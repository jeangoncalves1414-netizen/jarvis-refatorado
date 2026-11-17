package com.example.jarvismobile

import android.content.Context
import android.media.AudioFormat
import android.media.AudioRecord
import android.media.MediaRecorder
import android.os.Handler
import android.os.Looper
import android.util.Base64
import android.webkit.JavascriptInterface
import android.webkit.WebView
import org.json.JSONObject
import java.io.ByteArrayOutputStream
import kotlin.concurrent.thread
import kotlin.math.sqrt

/** Silent microphone capture. Transcription stays in the protected cloud endpoint. */
class NativeSpeechBridge(private val context: Context, private val page: WebView) {
    private val main = Handler(Looper.getMainLooper())
    @Volatile private var listening = false
    @Volatile private var capturing = false
    @Volatile private var continuous = false

    @JavascriptInterface fun startSpeech(continuousMode: Boolean) {
        if (capturing) return
        continuous = continuousMode
        listening = true
        capturing = true
        thread(name = "jarvis-mic") { captureUtterance() }
    }

    @JavascriptInterface fun stopSpeech() {
        listening = false
        capturing = false
    }

    fun destroy() = stopSpeech()

    private fun captureUtterance() {
        val rate = 16_000
        val minBuffer = AudioRecord.getMinBufferSize(rate, AudioFormat.CHANNEL_IN_MONO, AudioFormat.ENCODING_PCM_16BIT)
        if (minBuffer <= 0) { failed("unavailable"); return }
        val recorder = try {
            AudioRecord(MediaRecorder.AudioSource.MIC, rate, AudioFormat.CHANNEL_IN_MONO,
                AudioFormat.ENCODING_PCM_16BIT, minBuffer * 2)
        } catch (_: Exception) { failed("unavailable"); return }
        if (recorder.state != AudioRecord.STATE_INITIALIZED) { recorder.release(); failed("unavailable"); return }

        val buffer = ByteArray(minBuffer)
        val pcm = ByteArrayOutputStream()
        var speaking = false
        var silenceAt = 0L
        val startedAt = System.currentTimeMillis()
        val calibrationUntil = startedAt + 300L
        var noiseTotal = 0.0
        var noiseFrames = 0
        try {
            recorder.startRecording()
            while (capturing && listening) {
                val count = recorder.read(buffer, 0, buffer.size)
                if (count <= 0) continue
                val rms = rms(buffer, count)
                val now = System.currentTimeMillis()
                pcm.write(buffer, 0, count) // Keep the first syllable, even while calibrating.
                if (now < calibrationUntil) {
                    noiseTotal += rms
                    noiseFrames++
                    continue
                }
                val noiseFloor = if (noiseFrames == 0) 0.0 else noiseTotal / noiseFrames
                val voiceThreshold = maxOf(100.0, noiseFloor * 1.25)
                val hasVoice = rms >= voiceThreshold
                if (hasVoice) { speaking = true; silenceAt = 0L }
                if (speaking && !hasVoice) {
                    if (silenceAt == 0L) silenceAt = now
                    if (now - silenceAt >= 1_000L) break
                }
                if (now - startedAt >= 12_000L) break
            }
        } catch (_: Exception) { failed("unavailable"); return
        } finally {
            capturing = false
            runCatching { recorder.stop() }
            recorder.release()
        }
        if (listening && pcm.size() >= rate / 4) emit("onSpeechAudio", Base64.encodeToString(wav(pcm.toByteArray(), rate), Base64.NO_WRAP))
        else if (listening && continuous) main.postDelayed({ startSpeech(true) }, 250L)
    }

    private fun rms(bytes: ByteArray, count: Int): Double {
        var total = 0.0
        var samples = 0
        var index = 0
        while (index + 1 < count) {
            val sample = ((bytes[index + 1].toInt() shl 8) or (bytes[index].toInt() and 0xff)).toShort().toInt()
            total += sample.toDouble() * sample
            samples++
            index += 2
        }
        return if (samples == 0) 0.0 else sqrt(total / samples)
    }

    private fun wav(pcm: ByteArray, rate: Int): ByteArray {
        val header = ByteArray(44)
        fun put(offset: Int, value: Int, bytes: Int) { repeat(bytes) { header[offset + it] = (value shr (it * 8)).toByte() } }
        header[0] = 'R'.code.toByte(); header[1] = 'I'.code.toByte(); header[2] = 'F'.code.toByte(); header[3] = 'F'.code.toByte()
        put(4, 36 + pcm.size, 4); header[8] = 'W'.code.toByte(); header[9] = 'A'.code.toByte(); header[10] = 'V'.code.toByte(); header[11] = 'E'.code.toByte()
        header[12] = 'f'.code.toByte(); header[13] = 'm'.code.toByte(); header[14] = 't'.code.toByte(); header[15] = ' '.code.toByte()
        put(16, 16, 4); put(20, 1, 2); put(22, 1, 2); put(24, rate, 4); put(28, rate * 2, 4); put(32, 2, 2); put(34, 16, 2)
        header[36] = 'd'.code.toByte(); header[37] = 'a'.code.toByte(); header[38] = 't'.code.toByte(); header[39] = 'a'.code.toByte(); put(40, pcm.size, 4)
        return header + pcm
    }

    private fun failed(code: String) {
        capturing = false
        emit("onSpeechError", code)
    }

    private fun emit(method: String, value: String) {
        val payload = JSONObject.quote(value)
        page.post { page.evaluateJavascript("(function(){window.__jarvisNativeVoice?.$method?.($payload)})()", null) }
    }
}
