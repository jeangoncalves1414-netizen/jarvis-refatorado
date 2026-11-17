package com.example.jarvismobile

import android.app.*
import android.content.*
import android.content.pm.PackageManager
import android.database.Cursor
import android.speech.tts.TextToSpeech
import java.util.Locale
import android.media.MediaPlayer
import android.net.Uri
import android.os.*
import android.provider.Settings
import android.webkit.*
import android.widget.Toast
import org.json.JSONObject
import java.io.File
import java.net.URL
import javax.net.ssl.HttpsURLConnection

private const val EMPTY = """{"rev":0,"habits":[],"finance":[],"queue":[],"synced":""}"""
internal object RoutineStore {
    fun read(c: Context) = c.getSharedPreferences("routine", 0).getString("data", EMPTY)!!
    @Synchronized fun save(c: Context, data: String): Boolean {
        val next = JSONObject(data)
        val rev = next.getLong("rev")
        if (JSONObject(read(c)).getLong("rev") != rev) return false
        next.put("rev", rev + 1)
        return c.getSharedPreferences("routine", 0).edit().putString("data", next.toString()).commit()
    }
}

// The USB helper transfers files through run-as. Only the Android shell can request a snapshot/commit.
class RoutineTransfer : ContentProvider() {
    override fun onCreate() = true
    override fun call(method: String, arg: String?, extras: Bundle?): Bundle {
        check(Binder.getCallingUid() == 2000 || Binder.getCallingUid() == 0)
        val c = requireNotNull(context)
        val ok = when(method) {
            "pair" -> {
                val file = File(c.filesDir, "pair.json")
                val cfg = JSONObject(file.readText())
                settings(c).edit().putString("wifiPair", cfg.toString()).commit()
                file.delete()
                WifiRoutine.setup(c)
                true
            }
            "export" -> { File(c.filesDir, "routine-out.json").writeText(RoutineStore.read(c)); true }
            "import" -> RoutineStore.save(c, File(c.filesDir, "routine-in.json").readText())
            else -> false
        }
        return Bundle().apply { putBoolean("ok", ok) }
    }
    override fun query(u: Uri,p: Array<out String>?,s: String?,a: Array<out String>?,o: String?): Cursor? = null
    override fun getType(u: Uri): String? = null
    override fun insert(u: Uri,v: ContentValues?): Uri? = null
    override fun delete(u: Uri,s: String?,a: Array<out String>?) = 0
    override fun update(u: Uri,v: ContentValues?,s: String?,a: Array<out String>?) = 0
}

class RoutineActivity : Activity() {
    private lateinit var page: WebView
    private var motivation: MediaPlayer? = null
    private var voice: TextToSpeech? = null
    private var portuguese = false
    private var voiceReady = false
    private var pendingReading: String? = null
    private var morning = false
    private val updates = SharedPreferences.OnSharedPreferenceChangeListener { _, key ->
        if (key == "data") page.post { page.evaluateJavascript("window.refresh && refresh()", null) }
    }
    override fun onCreate(state: Bundle?) {
        super.onCreate(state)
        morning = intent.action == "morning" && state == null
        window.statusBarColor = 0xff0e1b21.toInt()
        window.navigationBarColor = window.statusBarColor
        page = WebView(this)
        page.settings.javaScriptEnabled = true
        page.settings.allowContentAccess = false
        page.settings.allowFileAccess = false
        page.addJavascriptInterface(Bridge(), "Routine")
        page.webViewClient = object : WebViewClient() {
            override fun shouldOverrideUrlLoading(v: WebView, request: WebResourceRequest) = true
            override fun onPageFinished(v: WebView, url: String) { showMorning() }
        }
        setContentView(page)
        page.loadDataWithBaseURL("https://routine.invalid/", assets.open("routine.html").bufferedReader().use { it.readText() }, "text/html", "UTF-8", null)
    }
    private fun showMorning() {
        if (!morning) return
        morning = false
        page.evaluateJavascript("show('morning')", null)
        motivation?.release()
        motivation = alarmAudio(this, R.raw.motivacao).apply {
            setOnCompletionListener {
                if (!isFinishing && !isDestroyed) page.evaluateJavascript("spokenMorning()") { json ->
                    val text = org.json.JSONTokener(json).nextValue() as? String
                    if (!text.isNullOrBlank()) readMorning(text)
                }
            }
            start()
        }
    }
    private fun readMorning(text: String) {
        val origin = getString(R.string.panel_origin)
        if (origin.isEmpty()) return
        val cookie = CookieManager.getInstance().getCookie(origin) ?: return
        val intro = motivation
        Thread {
            val file = try { File.createTempFile("morning-", ".mp3", cacheDir) }
                catch (_: java.io.IOException) { return@Thread }
            try {
                val connection = URL("$origin/api/voice/tts").openConnection() as HttpsURLConnection
                try {
                    connection.instanceFollowRedirects = false
                    connection.connectTimeout = 3000
                    connection.readTimeout = 15000
                    connection.requestMethod = "POST"
                    connection.doOutput = true
                    connection.setRequestProperty("Cookie", cookie)
                    connection.setRequestProperty("Content-Type", "application/json")
                    connection.outputStream.use { it.write(JSONObject().put("text", text).toString().toByteArray()) }
                    if (connection.responseCode != 200 || connection.contentType?.startsWith("audio/") != true) return@Thread
                    connection.inputStream.use { input -> file.outputStream().use { input.copyTo(it) } }
                } finally { connection.disconnect() }
                val player = MediaPlayer()
                try {
                    player.setAudioAttributes(android.media.AudioAttributes.Builder()
                        .setUsage(android.media.AudioAttributes.USAGE_ALARM)
                        .setContentType(android.media.AudioAttributes.CONTENT_TYPE_SPEECH).build())
                    player.setDataSource(file.absolutePath)
                    player.prepare()
                } catch (e: Exception) { player.release(); throw e }
                runOnUiThread {
                    if (isFinishing || isDestroyed || motivation !== intro || !hasWindowFocus()) player.release()
                    else { intro?.release(); motivation = player; player.start() }
                }
            } catch (_: Exception) {
                // The prerecorded greeting still plays offline; the summary is also visible.
            } finally { file.delete() }
        }.start()
    }
    private fun prepareVoice() {
        if (voice != null) return
        voice = TextToSpeech(this) { status -> runOnUiThread {
            if (isDestroyed) return@runOnUiThread
            val result = voice?.setLanguage(Locale.forLanguageTag("pt-BR"))
            portuguese = status == TextToSpeech.SUCCESS && result != null && result >= 0
            voiceReady = true
            pendingReading?.let { readAloud(it) }
            pendingReading = null
        } }
    }
    private fun readAloud(text: String) {
        if (!portuguese || voice?.speak(text, TextToSpeech.QUEUE_FLUSH, null, "chat") != TextToSpeech.SUCCESS)
            Toast.makeText(this, "Voz em português indisponível no Android.", Toast.LENGTH_SHORT).show()
    }
    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        setIntent(intent)
        morning = intent.action == "morning"
        showMorning()
    }
    private val syncUpdates = SharedPreferences.OnSharedPreferenceChangeListener { _, key ->
        if (key == "wifiStatus") page.post { page.evaluateJavascript("window.syncLabel && syncLabel()", null) }
    }
    override fun onResume() {
        super.onResume()
        settings(this).registerOnSharedPreferenceChangeListener(syncUpdates)
        if (settings(this).contains("wifiPair")) WifiRoutine.start(this)
        getSharedPreferences("routine", 0).registerOnSharedPreferenceChangeListener(updates)
        page.evaluateJavascript("window.refresh && refresh()", null)
        if (!morning && settings(this).getBoolean("ringing", false) && intent.action != "morning")
            startActivity(Intent(this, WakeActivity::class.java))
    }
    override fun onPause() {
        getSharedPreferences("routine", 0).unregisterOnSharedPreferenceChangeListener(updates)
        settings(this).unregisterOnSharedPreferenceChangeListener(syncUpdates)
        super.onPause()
    }
    override fun onDestroy() { motivation?.release(); voice?.shutdown(); page.destroy(); super.onDestroy() }
    inner class Bridge {
        @JavascriptInterface fun copyMessage(text: String) = runOnUiThread {
            getSystemService(ClipboardManager::class.java).setPrimaryClip(ClipData.newPlainText("Jarvis", text))
        }
        @JavascriptInterface fun readMessage(text: String) = runOnUiThread {
            if (voiceReady) readAloud(text) else {
                pendingReading = text
                prepareVoice()
            }
        }
        @JavascriptInterface fun data() = RoutineStore.read(this@RoutineActivity)
        @JavascriptInterface fun save(data: String) = RoutineStore.save(this@RoutineActivity, data)
        @JavascriptInterface fun weekTimes() = week(this@RoutineActivity).joinToString("|")
        @JavascriptInterface fun nextRing() = settings(this@RoutineActivity).getLong("next", 0L).toString()
        @JavascriptInterface fun morningPins() = settings(this@RoutineActivity).getString("morningPins", "[]")
        @JavascriptInterface fun storePins(ids: String) { settings(this@RoutineActivity).edit().putString("morningPins", ids).apply() }
        @JavascriptInterface fun chatHistory() = settings(this@RoutineActivity).getString("chat", "[]")
        @JavascriptInterface fun storeChat(history: String) { settings(this@RoutineActivity).edit().putString("chat", history).apply() }
        @JavascriptInterface fun syncStatus() = WifiRoutine.status(this@RoutineActivity)
        @JavascriptInterface fun syncNow() { WifiRoutine.start(this@RoutineActivity) }
        @JavascriptInterface fun setAlarm(weekText: String): String {
            val c = this@RoutineActivity
            val times = if (weekText.isEmpty()) List(7) { "" } else weekText.split('|')
            val active = times.any { it.isNotEmpty() }
            if (active && Build.VERSION.SDK_INT >= 33 && checkSelfPermission(android.Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) {
                runOnUiThread { requestPermissions(arrayOf(android.Manifest.permission.POST_NOTIFICATIONS), 2) }
                return "Autorize as notificações e toque em Salvar novamente."
            }
            return try {
                schedule(c, times, 0L)
                settings(c).edit().putString("week", times.joinToString("|")).remove("alarm").remove("snooze").commit()
                if (active) "Horários salvos." else "Despertador desligado."
            } catch (_: IllegalArgumentException) {
                "Confira os horários." 
            } catch (e: SecurityException) {
                if (Build.VERSION.SDK_INT >= 31) runOnUiThread {
                    startActivity(Intent(Settings.ACTION_REQUEST_SCHEDULE_EXACT_ALARM, Uri.parse("package:" + packageName)))
                }
                "Permita alarmes exatos e salve novamente."
            }
        }
        @JavascriptInterface fun preview() = runOnUiThread {
            startForegroundService(Intent(this@RoutineActivity, RingService::class.java))
            startActivity(Intent(this@RoutineActivity, WakeActivity::class.java))
        }
    }
}

