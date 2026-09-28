package com.example.jarvismobile

import android.content.Context
import android.content.Intent
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.speech.RecognitionListener
import android.speech.RecognizerIntent
import android.speech.SpeechRecognizer
import android.speech.tts.TextToSpeech
import android.speech.tts.UtteranceProgressListener
import android.util.Log
import android.webkit.WebView
import org.json.JSONObject
import java.util.Locale
import java.util.UUID

private const val TAG = "NativeVoiceBridge"

/** STT/TTS nativos do Android para o WebView standalone (sem o nucleo Python do PC). */
class NativeVoiceBridge(private val context: Context) {
    private val main = Handler(Looper.getMainLooper())
    private var webView: WebView? = null
    private var recognizer: SpeechRecognizer? = null
    private var tts: TextToSpeech? = null
    private var continuous = false
    private var listening = false
    // Guard against concurrent beginListen() calls (race between error-retry and JS-restart)
    private var isStartingListen = false

    fun attach(webView: WebView) {
        this.webView = webView
        if (tts == null) {
            tts = TextToSpeech(context) { status ->
                if (status == TextToSpeech.SUCCESS) {
                    val pt = Locale("pt", "BR")
                    val engine = tts ?: return@TextToSpeech
                    val result = engine.setLanguage(pt)
                    if (result == TextToSpeech.LANG_MISSING_DATA || result == TextToSpeech.LANG_NOT_SUPPORTED) {
                        engine.language = Locale.getDefault()
                    }
                }
            }
            tts?.setOnUtteranceProgressListener(object : UtteranceProgressListener() {
                override fun onStart(utteranceId: String?) {
                    emit("onTtsStart", utteranceId ?: "")
                }

                override fun onDone(utteranceId: String?) {
                    emit("onTtsDone", utteranceId ?: "")
                }

                @Deprecated("Deprecated in Java")
                override fun onError(utteranceId: String?) {
                    emit("onTtsError", utteranceId ?: "")
                }
            })
        }
    }

    fun startListening(continuousMode: Boolean) {
        continuous = continuousMode
        listening = true
        beginListen()
    }

    fun stopListening() {
        listening = false
        continuous = false
        try {
            recognizer?.stopListening()
        } catch (_: Exception) {
        }
        try {
            recognizer?.cancel()
        } catch (_: Exception) {
        }
    }

    fun speak(text: String) {
        val engine = tts ?: return
        if (text.isBlank()) return
        val id = UUID.randomUUID().toString()
        engine.speak(text, TextToSpeech.QUEUE_FLUSH, Bundle(), id)
    }

    fun stopSpeak() {
        try {
            tts?.stop()
        } catch (_: Exception) {
        }
    }

    fun destroy() {
        listening = false
        try {
            recognizer?.destroy()
        } catch (_: Exception) {
        }
        recognizer = null
        try {
            tts?.shutdown()
        } catch (_: Exception) {
        }
        tts = null
        webView = null
    }

    private fun beginListen() {
        if (!listening) return
        // Guard: prevent concurrent starts from race between Kotlin retry and JS restart
        if (isStartingListen) {
            Log.w(TAG, "beginListen() skipped – already starting")
            return
        }
        isStartingListen = true
        Log.d(TAG, "beginListen() called – listening=$listening continuous=$continuous")
        // NOTE: We intentionally skip isRecognitionAvailable() here.
        // On budget devices (e.g. Moto E20 / Android Go) it can return false even when
        // the Google recognition service IS available through the Google app.
        // We just try and let any real failure come through onError() callbacks.
        // Android SpeechRecognizer CANNOT be reused after stopListening().
        // Always destroy the old instance and create a fresh one to avoid silent failures.
        try {
            recognizer?.cancel()
            recognizer?.destroy()
        } catch (e: Exception) {
            Log.w(TAG, "Error destroying old recognizer: ${e.message}")
        }
        recognizer = SpeechRecognizer.createSpeechRecognizer(context).apply {
            setRecognitionListener(listener)
        }
        Log.d(TAG, "New SpeechRecognizer created")
        val intent = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH).apply {
            putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
            putExtra(RecognizerIntent.EXTRA_LANGUAGE, "pt-BR")
            putExtra(RecognizerIntent.EXTRA_LANGUAGE_PREFERENCE, "pt-BR")
            putExtra(RecognizerIntent.EXTRA_PARTIAL_RESULTS, true)
            putExtra(RecognizerIntent.EXTRA_MAX_RESULTS, 1)
            putExtra(RecognizerIntent.EXTRA_SPEECH_INPUT_MINIMUM_LENGTH_MILLIS, 300L)
            putExtra(RecognizerIntent.EXTRA_SPEECH_INPUT_COMPLETE_SILENCE_LENGTH_MILLIS, 1200L)
            putExtra(RecognizerIntent.EXTRA_SPEECH_INPUT_POSSIBLY_COMPLETE_SILENCE_LENGTH_MILLIS, 800L)
            putExtra(RecognizerIntent.EXTRA_CALLING_PACKAGE, context.packageName)
        }
        try {
            recognizer?.startListening(intent)
            Log.d(TAG, "startListening() dispatched successfully")
        } catch (error: Exception) {
            Log.e(TAG, "startListening() threw: ${error.message}")
            emit("onSpeechError", error.message ?: "start-failed")
        } finally {
            isStartingListen = false
        }
    }

    private val listener = object : RecognitionListener {
        override fun onReadyForSpeech(params: Bundle?) {
            Log.d(TAG, "onReadyForSpeech – microphone open and ready")
        }
        override fun onBeginningOfSpeech() {
            Log.d(TAG, "onBeginningOfSpeech – audio detected")
        }
        override fun onRmsChanged(rmsdB: Float) {
            // Logged sparsely to avoid flooding
        }
        override fun onBufferReceived(buffer: ByteArray?) {}
        override fun onEndOfSpeech() {
            Log.d(TAG, "onEndOfSpeech")
        }

        override fun onError(error: Int) {
            val code = when (error) {
                SpeechRecognizer.ERROR_NO_MATCH -> "no-match"
                SpeechRecognizer.ERROR_SPEECH_TIMEOUT -> "timeout"
                SpeechRecognizer.ERROR_CLIENT -> "client"
                SpeechRecognizer.ERROR_INSUFFICIENT_PERMISSIONS -> "permission"
                SpeechRecognizer.ERROR_NETWORK, SpeechRecognizer.ERROR_NETWORK_TIMEOUT -> "network"
                SpeechRecognizer.ERROR_RECOGNIZER_BUSY -> "busy"
                SpeechRecognizer.ERROR_AUDIO -> "audio"
                else -> "error-$error"
            }
            Log.w(TAG, "onError: $code (raw=$error) listening=$listening continuous=$continuous")
            emit("onSpeechError", code)
            emit("onSpeechEnd", code)
            // busy errors need a longer delay before retry so the system can release resources
            val retryable = error != SpeechRecognizer.ERROR_INSUFFICIENT_PERMISSIONS &&
                error != SpeechRecognizer.ERROR_CLIENT
            if (listening && continuous && retryable) {
                val delay = if (error == SpeechRecognizer.ERROR_RECOGNIZER_BUSY) 600L else 320L
                main.postDelayed({ if (listening) beginListen() }, delay)
            }
        }

        override fun onResults(results: Bundle?) {
            val text = results
                ?.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)
                ?.firstOrNull()
                .orEmpty()
            Log.d(TAG, "onResults: \"$text\" listening=$listening continuous=$continuous")
            if (text.isNotBlank()) emit("onSpeechFinal", text)
            emit("onSpeechEnd", "ok")
            // In continuous mode: if text was empty (no speech detected), restart immediately.
            // If text was found, JS will call startSpeech(true) again after processing the reply.
            if (listening && continuous && text.isBlank()) {
                main.postDelayed({ if (listening) beginListen() }, 200)
            }
        }

        override fun onPartialResults(partialResults: Bundle?) {
            val text = partialResults
                ?.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)
                ?.firstOrNull()
                .orEmpty()
            if (text.isNotBlank()) {
                Log.d(TAG, "onPartialResults: \"$text\"")
                emit("onSpeechPartial", text)
            }
        }

        override fun onEvent(eventType: Int, params: Bundle?) {}
    }

    private fun emit(fn: String, value: String) {
        val payload = JSONObject.quote(value)
        main.post {
            webView?.evaluateJavascript(
                "(function(){var h=window.__jarvisNativeVoice;if(h&&typeof h.$fn==='function'){h.$fn($payload);}})();",
                null,
            )
        }
    }
}
