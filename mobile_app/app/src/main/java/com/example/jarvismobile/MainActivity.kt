package com.example.jarvismobile

import android.Manifest
import android.content.Context
import android.content.pm.PackageManager
import android.graphics.Color
import android.os.Build
import android.os.Bundle
import android.os.VibrationEffect
import android.os.Vibrator
import android.os.VibratorManager
import android.view.View
import android.webkit.JavascriptInterface
import android.webkit.PermissionRequest
import android.webkit.WebChromeClient
import android.webkit.WebResourceRequest
import android.webkit.WebResourceResponse
import android.webkit.WebSettings
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.FrameLayout
import androidx.activity.ComponentActivity
import androidx.core.app.ActivityCompat
import androidx.core.content.ContextCompat
import androidx.core.view.ViewCompat
import androidx.core.view.WindowCompat
import androidx.core.view.WindowInsetsCompat
import androidx.webkit.WebViewAssetLoader
import java.io.BufferedReader
import java.io.InputStreamReader
import java.net.HttpURLConnection
import java.net.URL
import java.util.concurrent.ConcurrentHashMap
import org.json.JSONObject

class MainActivity : ComponentActivity() {

    internal lateinit var webView: WebView
    private lateinit var voiceBridge: NativeVoiceBridge

    @Suppress("DEPRECATION")
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        WindowCompat.setDecorFitsSystemWindows(window, false)
        window.statusBarColor = Color.parseColor("#09090D")
        window.navigationBarColor = Color.parseColor("#09090D")

        checkPermissions()
        voiceBridge = NativeVoiceBridge(this)

        val statusBarFallback = run {
            val id = resources.getIdentifier("status_bar_height", "dimen", "android")
            if (id > 0) resources.getDimensionPixelSize(id) else (24 * resources.displayMetrics.density).toInt()
        }

        val root = FrameLayout(this).apply {
            setBackgroundColor(Color.parseColor("#09090D"))
            clipToPadding = true
            clipChildren = true
        }
        val assetLoader = WebViewAssetLoader.Builder()
            .addPathHandler("/", WebViewAssetLoader.AssetsPathHandler(this))
            .build()

        webView = WebView(this).apply {
            layoutParams = FrameLayout.LayoutParams(-1, -1).apply {
                setMargins(0, statusBarFallback, 0, 0)
            }
            settings.apply {
                javaScriptEnabled = true
                domStorageEnabled = true
                useWideViewPort = true
                loadWithOverviewMode = true
                mediaPlaybackRequiresUserGesture = false
                allowFileAccess = false
                allowContentAccess = false
                allowFileAccessFromFileURLs = false
                allowUniversalAccessFromFileURLs = false
                cacheMode = WebSettings.LOAD_NO_CACHE
                mixedContentMode = WebSettings.MIXED_CONTENT_ALWAYS_ALLOW
                setSupportZoom(false)
                builtInZoomControls = false
                displayZoomControls = false
            }

            clearCache(true)
            setLayerType(View.LAYER_TYPE_HARDWARE, null)

            WebView.setWebContentsDebuggingEnabled(true)
            webChromeClient = object : WebChromeClient() {
                override fun onPermissionRequest(request: PermissionRequest?) {
                    runOnUiThread {
                        request?.grant(request.resources)
                    }
                }

                override fun onConsoleMessage(consoleMessage: android.webkit.ConsoleMessage?): Boolean {
                    android.util.Log.d("JarvisWeb", "${consoleMessage?.message()} [${consoleMessage?.sourceId()}:${consoleMessage?.lineNumber()}]")
                    return true
                }
            }

            webViewClient = object : WebViewClient() {
                override fun shouldOverrideUrlLoading(view: WebView?, request: WebResourceRequest?): Boolean {
                    return false
                }

                override fun shouldInterceptRequest(view: WebView?, request: WebResourceRequest?): WebResourceResponse? {
                    return request?.url?.let(assetLoader::shouldInterceptRequest)
                        ?: super.shouldInterceptRequest(view, request)
                }

                override fun onReceivedSslError(view: WebView?, handler: android.webkit.SslErrorHandler?, error: android.net.http.SslError?) {
                    android.util.Log.w("JarvisWeb", "SSL Error: $error")
                    super.onReceivedSslError(view, handler, error)
                }
            }

            addJavascriptInterface(WebAppInterface(this@MainActivity), "Android")
        }
        voiceBridge.attach(webView)
        root.addView(webView)
        ViewCompat.setOnApplyWindowInsetsListener(root) { _, insets ->
            val bars = insets.getInsets(WindowInsetsCompat.Type.systemBars())
            val ime = insets.getInsets(WindowInsetsCompat.Type.ime())
            val top = maxOf(bars.top, statusBarFallback)
            val bottom = maxOf(bars.bottom, ime.bottom)
            val params = (webView.layoutParams as FrameLayout.LayoutParams).apply {
                setMargins(bars.left, top, bars.right, bottom)
            }
            webView.layoutParams = params
            WindowInsetsCompat.CONSUMED
        }

        setContentView(root)
        ViewCompat.requestApplyInsets(root)
        
        // Inject server URL configuration from intent or default to localhost
        val serverUrl = intent.getStringExtra("server_url") ?: "http://localhost:8000"
        webView.evaluateJavascript(
            """
            window.__JARVIS_SERVER_URL__ = "$serverUrl";
            window.addEventListener('DOMContentLoaded', function() {
                if (window.localStorage) {
                    window.localStorage.setItem('jarvis_server_url', "$serverUrl");
                }
            });
            """.trimIndent(),
            null
        )
        
        webView.loadUrl("https://appassets.androidplatform.net/index.html")
    }

    override fun onDestroy() {
        if (::voiceBridge.isInitialized) voiceBridge.destroy()
        super.onDestroy()
    }

    private fun checkPermissions() {
        val permissions = arrayOf(
            Manifest.permission.RECORD_AUDIO,
            Manifest.permission.CAMERA,
            Manifest.permission.VIBRATE,
        )
        val missing = permissions.filter {
            ContextCompat.checkSelfPermission(this, it) != PackageManager.PERMISSION_GRANTED
        }
        if (missing.isNotEmpty()) {
            ActivityCompat.requestPermissions(this, missing.toTypedArray(), 100)
        }
    }

    @Suppress("DEPRECATION")
    override fun onBackPressed() {
        if (::webView.isInitialized && webView.canGoBack()) {
            webView.goBack()
        } else {
            super.onBackPressed()
        }
    }

    class WebAppInterface(private val activity: MainActivity) {
        private val activeConnections = ConcurrentHashMap<String, HttpURLConnection>()

        @JavascriptInterface
        fun nativePostStream(requestId: String, urlStr: String, headersJson: String, bodyStr: String) {
            Thread {
                var conn: HttpURLConnection? = null
                try {
                    val url = URL(urlStr)
                    conn = (url.openConnection() as HttpURLConnection).apply {
                        requestMethod = "POST"
                        doOutput = true
                        connectTimeout = 20000
                        readTimeout = 60000
                        useCaches = false
                        try {
                            val headersObj = JSONObject(headersJson)
                            val keys = headersObj.keys()
                            while (keys.hasNext()) {
                                val k = keys.next()
                                setRequestProperty(k, headersObj.getString(k))
                            }
                        } catch (_: Exception) {}
                    }
                    activeConnections[requestId] = conn
                    conn.outputStream.use { os ->
                        os.write(bodyStr.toByteArray(Charsets.UTF_8))
                        os.flush()
                    }

                    val responseCode = conn.responseCode
                    val isSuccess = responseCode in 200..299
                    val stream = if (isSuccess) conn.inputStream else (conn.errorStream ?: conn.inputStream)
                    val reader = BufferedReader(InputStreamReader(stream, Charsets.UTF_8))
                    var line: String? = reader.readLine()
                    val errorBuffer = StringBuilder()

                    while (line != null) {
                        if (isSuccess) {
                            val escaped = JSONObject.quote(line)
                            activity.runOnUiThread {
                                activity.webView.evaluateJavascript(
                                    "window.__onNativeStreamChunk && window.__onNativeStreamChunk('$requestId', $escaped);",
                                    null
                                )
                            }
                        } else {
                            errorBuffer.append(line).append("\n")
                        }
                        line = reader.readLine()
                    }
                    reader.close()

                    activity.runOnUiThread {
                        if (isSuccess) {
                            activity.webView.evaluateJavascript(
                                "window.__onNativeStreamDone && window.__onNativeStreamDone('$requestId');",
                                null
                            )
                        } else {
                            val errMsg = "HTTP $responseCode: ${errorBuffer.toString().take(300).trim()}"
                            val escaped = JSONObject.quote(errMsg)
                            activity.webView.evaluateJavascript(
                                "window.__onNativeStreamError && window.__onNativeStreamError('$requestId', $escaped);",
                                null
                            )
                        }
                    }
                } catch (e: Exception) {
                    val errEscaped = JSONObject.quote(e.message ?: "Erro de rede nativa")
                    activity.runOnUiThread {
                        activity.webView.evaluateJavascript(
                            "window.__onNativeStreamError && window.__onNativeStreamError('$requestId', $errEscaped);",
                            null
                        )
                    }
                } finally {
                    try { conn?.disconnect() } catch (_: Exception) {}
                    activeConnections.remove(requestId)
                }
            }.start()
        }

        @JavascriptInterface
        fun abortNativeStream(requestId: String) {
            try {
                activeConnections.remove(requestId)?.disconnect()
            } catch (_: Exception) {}
        }

        @JavascriptInterface
        fun vibrate(milliseconds: Long) {
            try {
                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
                    val vibratorManager = activity.getSystemService(Context.VIBRATOR_MANAGER_SERVICE) as VibratorManager
                    vibratorManager.defaultVibrator.vibrate(
                        VibrationEffect.createOneShot(milliseconds, VibrationEffect.DEFAULT_AMPLITUDE),
                    )
                } else {
                    @Suppress("DEPRECATION")
                    val vibrator = activity.getSystemService(Context.VIBRATOR_SERVICE) as Vibrator
                    vibrator.vibrate(milliseconds)
                }
            } catch (_: Exception) {
            }
        }

        @JavascriptInterface
        fun startSpeech(continuous: Boolean) {
            activity.runOnUiThread { activity.voiceBridge.startListening(continuous) }
        }

        @JavascriptInterface
        fun stopSpeech() {
            activity.runOnUiThread { activity.voiceBridge.stopListening() }
        }

        @JavascriptInterface
        fun speak(text: String) {
            activity.runOnUiThread { activity.voiceBridge.speak(text) }
        }

        @JavascriptInterface
        fun stopSpeak() {
            activity.runOnUiThread { activity.voiceBridge.stopSpeak() }
        }
    }
}
