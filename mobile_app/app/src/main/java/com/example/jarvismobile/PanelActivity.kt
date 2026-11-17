package com.example.jarvismobile

import android.Manifest
import android.app.Activity
import android.app.AlertDialog
import android.content.ActivityNotFoundException
import android.content.Intent
import android.content.pm.PackageManager
import android.graphics.Color
import android.net.Uri
import android.os.Bundle
import android.webkit.*
import android.widget.Toast
import java.io.File
import org.json.JSONObject

class PanelActivity : Activity() {
    private lateinit var page: WebView
    private val origin by lazy { getString(R.string.panel_origin) }
    private val cloudMode by lazy { getString(R.string.panel_mode) == "cloud" }
    private var dialog: AlertDialog? = null
    private var mediaRequest: PermissionRequest? = null
    private var picker: ValueCallback<Array<Uri>>? = null
    // The mobile panel deliberately supports only the microphone. Face and
    // voice identity capture belong to the desktop and are not used here.
    private val mediaPermissions = mapOf(
        PermissionRequest.RESOURCE_AUDIO_CAPTURE to Manifest.permission.RECORD_AUDIO
    )
    private val timeout = Runnable {
        options(if (cloudMode) "O Jarvis na nuvem demorou a responder. Verifique sua internet e tente novamente."
        else "O PC demorou a responder. Verifique o Wi-Fi e abra o Jarvis no computador.")
    }

    private fun paired(uri: Uri) = origin.isNotEmpty() && uri.scheme == "https" &&
        uri.encodedAuthority == Uri.parse(origin).encodedAuthority

    override fun onCreate(state: Bundle?) {
        super.onCreate(state)
        window.statusBarColor = Color.rgb(16, 17, 21)
        window.navigationBarColor = window.statusBarColor
        page = WebView(this)
        setContentView(page)
        page.setBackgroundColor(window.statusBarColor)
        page.settings.apply {
            javaScriptEnabled = true
            domStorageEnabled = true
            allowFileAccess = false
            allowContentAccess = false
            mediaPlaybackRequiresUserGesture = false
            userAgentString = "$userAgentString JarvisMobile/1.8.1"
        }
        page.webViewClient = object : WebViewClient() {
            override fun shouldOverrideUrlLoading(view: WebView, request: WebResourceRequest): Boolean {
                if (!request.isForMainFrame || paired(request.url)) return false
                if (request.hasGesture() && request.url.scheme in setOf("http", "https")) {
                    try { startActivity(Intent(Intent.ACTION_VIEW, request.url)) }
                    catch (_: ActivityNotFoundException) { Toast.makeText(this@PanelActivity, "Navegador indisponível.", Toast.LENGTH_SHORT).show() }
                }
                return true
            }
            override fun onPageCommitVisible(view: WebView, url: String) { page.removeCallbacks(timeout) }
            override fun onReceivedError(view: WebView, request: WebResourceRequest, error: WebResourceError) {
                if (request.isForMainFrame) options(if (cloudMode) "Não foi possível alcançar o Jarvis na nuvem." else "Abra o Jarvis no PC e conecte o celular ao mesmo Wi-Fi.")
            }
            override fun onReceivedHttpError(view: WebView, request: WebResourceRequest, response: WebResourceResponse) {
                if (request.isForMainFrame) options(if (cloudMode) "O Jarvis na nuvem recusou a conexão (HTTP ${response.statusCode})." else "O PC recusou a conexão (HTTP ${response.statusCode}). Verifique o pareamento.")
            }
        }
        page.webChromeClient = object : WebChromeClient() {
            override fun onPermissionRequest(request: PermissionRequest) {
                if (!paired(request.origin) || mediaRequest != null) { request.deny(); return }
                val needed = request.resources.mapNotNull { mediaPermissions[it] }.distinct()
                    .filter { checkSelfPermission(it) != PackageManager.PERMISSION_GRANTED }
                if (needed.isEmpty()) resolveMedia(request)
                else { mediaRequest = request; requestPermissions(needed.toTypedArray(), 1) }
            }
            override fun onPermissionRequestCanceled(request: PermissionRequest) {
                if (mediaRequest == request) mediaRequest = null
            }
            override fun onShowFileChooser(view: WebView, callback: ValueCallback<Array<Uri>>, params: FileChooserParams): Boolean {
                picker?.onReceiveValue(null)
                picker = callback
                try { startActivityForResult(params.createIntent(), 2) }
                catch (_: ActivityNotFoundException) { picker = null; callback.onReceiveValue(null) }
                return true
            }
        }
        if (state == null) WifiRoutine.start(this)
        connect()
    }

    private fun resolveMedia(request: PermissionRequest) {
        val granted = request.resources.filter {
            mediaPermissions[it]?.let { permission -> checkSelfPermission(permission) == PackageManager.PERMISSION_GRANTED } == true
        }
        if (granted.isEmpty()) request.deny() else request.grant(granted.toTypedArray())
    }

    override fun onRequestPermissionsResult(code: Int, permissions: Array<String>, results: IntArray) {
        super.onRequestPermissionsResult(code, permissions, results)
        if (code == 1) { mediaRequest?.let(::resolveMedia); mediaRequest = null }
    }

    override fun onActivityResult(code: Int, result: Int, data: Intent?) {
        super.onActivityResult(code, result, data)
        if (code == 2) {
            picker?.onReceiveValue(WebChromeClient.FileChooserParams.parseResult(result, data))
            picker = null
        }
    }

    private fun connect() {
        val config = runCatching { JSONObject(File(filesDir, "panel.json").readText()) }.getOrNull()
        val token = config?.optString("token").orEmpty()
        if (origin.isEmpty() || config?.optString("origin") != origin || !Regex("[a-zA-Z0-9_-]{40,100}").matches(token)) {
            options(if (cloudMode) "Conclua a configuração segura do painel móvel." else "Conclua o pareamento do painel com o PC por USB.")
            return
        }
        val cookieName = if (cloudMode) "__Host-jarvis_cloud" else "__Host-jarvis_panel"
        CookieManager.getInstance().setCookie(origin, "$cookieName=$token; Path=/; Secure; HttpOnly; SameSite=Strict") { saved ->
            if (isDestroyed || isFinishing) return@setCookie
            if (!saved) { options("Não foi possível iniciar a sessão do painel."); return@setCookie }
            page.removeCallbacks(timeout)
            page.postDelayed(timeout, 15000)
            page.loadUrl("$origin/app/")
        }
    }

    private fun options(message: String? = null) {
        page.removeCallbacks(timeout)
        if (isFinishing || isDestroyed || dialog?.isShowing == true) return
        val builder = AlertDialog.Builder(this).setTitle("Jarvis")
            .setPositiveButton(if (message == null) "Continuar no painel" else "Tentar novamente") { _, _ ->
                if (message != null) connect()
            }
            .setNeutralButton("Rotina offline") { _, _ -> startActivity(Intent(this, RoutineActivity::class.java)) }
            .setNegativeButton("Sair") { _, _ -> finish() }
        if (message != null) builder.setMessage(message)
        dialog = builder.show()
    }

    @Deprecated("Android back navigation")
    override fun onBackPressed() {
        if (page.canGoBack()) page.goBack() else options()
    }

    override fun onDestroy() {
        page.removeCallbacks(timeout)
        dialog?.dismiss()
        mediaRequest?.deny()
        picker?.onReceiveValue(null)
        page.destroy()
        super.onDestroy()
    }
}
