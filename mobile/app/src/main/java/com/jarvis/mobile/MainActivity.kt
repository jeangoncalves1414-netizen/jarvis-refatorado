package com.jarvis.mobile

import android.Manifest
import android.app.Activity
import android.content.Context
import android.content.Intent
import android.content.SharedPreferences
import android.content.pm.PackageManager
import android.graphics.Color
import android.os.Build
import android.os.Bundle
import android.speech.RecognitionListener
import android.speech.RecognizerIntent
import android.speech.SpeechRecognizer
import android.view.View
import android.webkit.WebChromeClient
import android.webkit.WebResourceError
import android.webkit.WebResourceRequest
import android.webkit.WebSettings
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.EditText
import android.widget.FrameLayout
import android.widget.ImageButton
import android.widget.LinearLayout
import android.widget.ProgressBar
import android.widget.Toast
import java.util.Locale

/**
 * Jarvis Mobile — Aplicativo Android Espelhado do Painel Jarvis PC.
 * Oferece interface espelhada em WebView com suporte nativo a Voz (STT),
 * comandos autônomos de IA, conexão USB via ADB Reverse ou Wi-Fi.
 */
class MainActivity : Activity() {

    private lateinit var webView: WebView
    private lateinit var progressBar: ProgressBar
    private lateinit var serverUrlInput: EditText
    private lateinit var configContainer: LinearLayout
    private lateinit var prefs: SharedPreferences
    private var speechRecognizer: SpeechRecognizer? = null

    private var serverUrl = "http://localhost:8000"

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        window.statusBarColor = Color.parseColor("#0D1117")

        prefs = getSharedPreferences("jarvis_mobile_prefs", Context.MODE_PRIVATE)
        serverUrl = prefs.getString("server_url", "http://localhost:8000") ?: "http://localhost:8000"

        buildUI()
        checkPermissions()
        initSpeechRecognizer()
    }

    private fun buildUI() {
        val root = FrameLayout(this)
        root.setBackgroundColor(Color.parseColor("#0A0F1A"))

        // WebView principal espelhado da interface Jarvis
        webView = WebView(this).apply {
            layoutParams = FrameLayout.LayoutParams(-1, -1)
            settings.javaScriptEnabled = true
            settings.domStorageEnabled = true
            settings.databaseEnabled = true
            settings.useWideViewPort = true
            settings.loadWithOverviewMode = true
            settings.cacheMode = WebSettings.LOAD_DEFAULT
            settings.mixedContentMode = WebSettings.MIXED_CONTENT_ALWAYS_ALLOW

            webViewClient = object : WebViewClient() {
                override fun onPageFinished(view: WebView?, url: String?) {
                    progressBar.visibility = View.GONE
                }

                override fun onReceivedError(
                    view: WebView?,
                    request: WebResourceRequest?,
                    error: WebResourceError?
                ) {
                    if (request?.isForMainFrame == true) {
                        progressBar.visibility = View.GONE
                        configContainer.visibility = View.VISIBLE
                        Toast.makeText(
                            this@MainActivity,
                            "Servidor inacessível em $serverUrl. Verifique o IP ou USB.",
                            Toast.LENGTH_LONG
                        ).show()
                    }
                }
            }
            webChromeClient = WebChromeClient()
        }
        root.addView(webView)

        // Loading Progress Bar
        progressBar = ProgressBar(this).apply {
            layoutParams = FrameLayout.LayoutParams(-2, -2, android.view.Gravity.CENTER)
            visibility = View.VISIBLE
        }
        root.addView(progressBar)

        // Overlay de Configuração Rápida do Servidor
        configContainer = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setBackgroundColor(Color.parseColor("#EE0D1117"))
            setPadding(24, 24, 24, 24)
            layoutParams = FrameLayout.LayoutParams(-1, -2, android.view.Gravity.TOP)
            visibility = View.GONE

            val row = LinearLayout(this@MainActivity).apply {
                orientation = LinearLayout.HORIZONTAL
            }

            serverUrlInput = EditText(this@MainActivity).apply {
                setText(serverUrl)
                setTextColor(Color.WHITE)
                setHintTextColor(Color.GRAY)
                hint = "http://192.168.0.44:8000 ou http://localhost:8000"
                textSize = 13f
                layoutParams = LinearLayout.LayoutParams(0, -2, 1f)
            }
            row.addView(serverUrlInput)

            val connectBtn = android.widget.Button(this@MainActivity).apply {
                text = "Conectar"
                textSize = 12f
                setOnClickListener {
                    var input = serverUrlInput.text.toString().trim()
                    if (!input.startsWith("http://") && !input.startsWith("https://")) {
                        input = "http://$input"
                    }
                    serverUrl = input
                    prefs.edit().putString("server_url", serverUrl).apply()
                    loadJarvisUI()
                    configContainer.visibility = View.GONE
                }
            }
            row.addView(connectBtn)
            addView(row)

            val usbBtn = android.widget.Button(this@MainActivity).apply {
                text = "Usar USB Debugging (localhost:8000)"
                textSize = 11f
                setOnClickListener {
                    serverUrl = "http://localhost:8000"
                    serverUrlInput.setText(serverUrl)
                    prefs.edit().putString("server_url", serverUrl).apply()
                    loadJarvisUI()
                    configContainer.visibility = View.GONE
                }
            }
            addView(usbBtn)
        }
        root.addView(configContainer)

        // Botão de Configuração (Engrenagem) no canto superior direito
        val configButton = ImageButton(this).apply {
            setImageResource(android.R.drawable.ic_menu_preferences)
            setBackgroundColor(Color.TRANSPARENT)
            setPadding(16, 16, 16, 16)
            layoutParams = FrameLayout.LayoutParams(-2, -2, android.view.Gravity.TOP or android.view.Gravity.END).apply {
                setMargins(0, 24, 24, 0)
            }
            setOnClickListener {
                configContainer.visibility = if (configContainer.visibility == View.VISIBLE) View.GONE else View.VISIBLE
            }
        }
        root.addView(configButton)

        // Botão Flutuante de Voz (Microfone) no canto inferior direito
        val micButton = ImageButton(this).apply {
            setImageResource(android.R.drawable.ic_btn_speak_now)
            setBackgroundColor(Color.parseColor("#00DAF8"))
            setPadding(24, 24, 24, 24)
            layoutParams = FrameLayout.LayoutParams(140, 140, android.view.Gravity.BOTTOM or android.view.Gravity.END).apply {
                setMargins(0, 0, 48, 48)
            }
            setOnClickListener {
                startVoiceRecognition()
            }
        }
        root.addView(micButton)

        setContentView(root)
        loadJarvisUI()
    }

    private fun loadJarvisUI() {
        progressBar.visibility = View.VISIBLE
        webView.loadUrl(serverUrl)
    }

    private fun checkPermissions() {
        if (Build.VERSION.SDK_INT >= 23) {
            val permissions = arrayOf(
                Manifest.permission.RECORD_AUDIO,
                Manifest.permission.INTERNET,
                Manifest.permission.CAMERA
            )
            val missing = permissions.filter { checkSelfPermission(it) != PackageManager.PERMISSION_GRANTED }
            if (missing.isNotEmpty()) {
                requestPermissions(missing.toTypedArray(), 101)
            }
        }
    }

    private fun initSpeechRecognizer() {
        if (SpeechRecognizer.isRecognitionAvailable(this)) {
            speechRecognizer = SpeechRecognizer.createSpeechRecognizer(this).apply {
                setRecognitionListener(object : RecognitionListener {
                    override fun onReadyForSpeech(params: Bundle?) {
                        Toast.makeText(this@MainActivity, "🎤 Ouvindo o Jarvis...", Toast.LENGTH_SHORT).show()
                    }
                    override fun onBeginningOfSpeech() {}
                    override fun onRmsChanged(rmsdB: Float) {}
                    override fun onBufferReceived(buffer: ByteArray?) {}
                    override fun onEndOfSpeech() {}
                    override fun onError(error: Int) {
                        Toast.makeText(this@MainActivity, "Erro de reconhecimento de voz.", Toast.LENGTH_SHORT).show()
                    }
                    override fun onResults(results: Bundle?) {
                        val matches = results?.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)
                        if (!matches.isNullOrEmpty()) {
                            val recognizedText = matches[0]
                            sendRecognizedTextToJarvis(recognizedText)
                        }
                    }
                    override fun onPartialResults(partialResults: Bundle?) {}
                    override fun onEvent(eventType: Int, params: Bundle?) {}
                })
            }
        }
    }

    private fun startVoiceRecognition() {
        val intent = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH).apply {
            putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
            putExtra(RecognizerIntent.EXTRA_LANGUAGE, Locale.getDefault())
        }
        speechRecognizer?.startListening(intent)
    }

    private fun sendRecognizedTextToJarvis(text: String) {
        val jsScript = "javascript:(function() { if (window.sendJarvisMessage) { window.sendJarvisMessage('$text'); } })()"
        webView.post { webView.loadUrl(jsScript) }
        Toast.makeText(this, "Comando enviado: $text", Toast.LENGTH_SHORT).show()
    }

    override fun onBackPressed() {
        if (webView.canGoBack()) {
            webView.goBack()
        } else {
            super.onBackPressed()
        }
    }

    override fun onDestroy() {
        speechRecognizer?.destroy()
        super.onDestroy()
    }
}
