package com.example.jarvismobile

import android.content.Context
import android.content.Intent
import android.media.AudioManager
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.speech.RecognitionListener
import android.speech.RecognizerIntent
import android.speech.SpeechRecognizer
import android.webkit.JavascriptInterface
import android.webkit.WebView
import org.json.JSONObject

/** Uses Android's proven speech service when this WebView cannot open its audio source. */
class NativeSpeechBridge(private val context: Context, private val page: WebView) {
    private val main = Handler(Looper.getMainLooper())
    private val audio = context.getSystemService(Context.AUDIO_SERVICE) as AudioManager
    private var recognizer: SpeechRecognizer? = null
    private var listening = false
    private var continuous = false
    private var mutedForRecognition = false

    @JavascriptInterface fun startSpeech(continuousMode: Boolean) = main.post {
        continuous = continuousMode
        listening = true
        beginListening()
    }

    @JavascriptInterface fun stopSpeech() = main.post {
        listening = false
        continuous = false
        runCatching { recognizer?.cancel() }
        restoreAudio()
    }

    fun destroy() = main.post {
        listening = false
        restoreAudio()
        runCatching { recognizer?.destroy() }
        recognizer = null
    }

    private fun beginListening() {
        if (!listening) return
        runCatching { recognizer?.destroy() }
        recognizer = runCatching { SpeechRecognizer.createSpeechRecognizer(context) }.getOrElse {
            emit("onSpeechError", "unavailable")
            return
        }.apply { setRecognitionListener(listener) }
        val intent = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH).apply {
            putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
            putExtra(RecognizerIntent.EXTRA_LANGUAGE, "pt-BR")
            putExtra(RecognizerIntent.EXTRA_PARTIAL_RESULTS, true)
            putExtra(RecognizerIntent.EXTRA_MAX_RESULTS, 1)
            // Give softer speech time to start and finish before the service closes the capture.
            putExtra(RecognizerIntent.EXTRA_SPEECH_INPUT_MINIMUM_LENGTH_MILLIS, 900L)
            putExtra(RecognizerIntent.EXTRA_SPEECH_INPUT_POSSIBLY_COMPLETE_SILENCE_LENGTH_MILLIS, 1_800L)
            putExtra(RecognizerIntent.EXTRA_SPEECH_INPUT_COMPLETE_SILENCE_LENGTH_MILLIS, 2_500L)
        }
        muteListeningSound()
        runCatching { recognizer?.startListening(intent) }.onFailure {
            restoreAudio()
            emit("onSpeechError", "unavailable")
        }
    }

    private val listener = object : RecognitionListener {
        override fun onReadyForSpeech(params: Bundle?) = Unit
        override fun onBeginningOfSpeech() = Unit
        override fun onRmsChanged(rmsdB: Float) = Unit
        override fun onBufferReceived(buffer: ByteArray?) = Unit
        override fun onEndOfSpeech() = Unit
        override fun onEvent(eventType: Int, params: Bundle?) = Unit

        override fun onPartialResults(results: Bundle?) {
            results?.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)?.firstOrNull()
                ?.takeIf { it.isNotBlank() }?.let { emit("onSpeechPartial", it) }
        }

        override fun onResults(results: Bundle?) {
            restoreAudio()
            val text = results?.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)?.firstOrNull().orEmpty()
            if (text.isNotBlank()) emit("onSpeechFinal", text)
            else retry()
        }

        override fun onError(error: Int) {
            restoreAudio()
            when (error) {
                SpeechRecognizer.ERROR_INSUFFICIENT_PERMISSIONS -> emit("onSpeechError", "permission")
                SpeechRecognizer.ERROR_CLIENT -> emit("onSpeechError", "client")
                else -> retry()
            }
        }
    }

    private fun muteListeningSound() {
        if (mutedForRecognition) return
        runCatching { audio.adjustStreamVolume(AudioManager.STREAM_MUSIC, AudioManager.ADJUST_MUTE, 0) }
        mutedForRecognition = true
    }

    private fun restoreAudio() {
        if (!mutedForRecognition) return
        runCatching { audio.adjustStreamVolume(AudioManager.STREAM_MUSIC, AudioManager.ADJUST_UNMUTE, 0) }
        mutedForRecognition = false
    }

    private fun retry() {
        if (listening && continuous) main.postDelayed({ beginListening() }, 350L)
    }

    private fun emit(method: String, value: String) {
        val payload = JSONObject.quote(value)
        page.post {
            page.evaluateJavascript("(function(){window.__jarvisNativeVoice?.$method?.($payload)})()", null)
        }
    }
}
