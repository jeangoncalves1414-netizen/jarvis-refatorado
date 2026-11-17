package com.example.jarvismobile

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.net.Uri
import android.os.IBinder
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.net.HttpURLConnection
import java.net.URL
import java.security.MessageDigest
import java.util.concurrent.Executors
import java.util.concurrent.TimeUnit

class RemoteControlService : Service() {
    private val worker = Executors.newSingleThreadScheduledExecutor()
    private lateinit var config: Config

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        if (intent?.action == STOP) { stopForeground(STOP_FOREGROUND_REMOVE); stopSelf(); return START_NOT_STICKY }
        config = readConfig(this) ?: run { stopSelf(); return START_NOT_STICKY }
        startForeground(ID, notification())
        worker.execute { request(config, "/api/remote/register", JSONObject().put("device_id", deviceId(this)).put("name", android.os.Build.MODEL)) }
        worker.scheduleWithFixedDelay({ poll(config) }, 2, 5, TimeUnit.SECONDS)
        return START_STICKY
    }

    override fun onDestroy() { worker.shutdownNow(); super.onDestroy() }

    private fun notification(): Notification {
        getSystemService(NotificationManager::class.java).createNotificationChannel(NotificationChannel(CHANNEL, "Controle remoto do Jarvis", NotificationManager.IMPORTANCE_LOW).apply { setSound(null, null) })
        val open = PendingIntent.getActivity(this, 91, Intent(this, PanelActivity::class.java), PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT)
        return Notification.Builder(this, CHANNEL).setSmallIcon(android.R.drawable.ic_menu_manage).setContentTitle("Controle remoto do Jarvis ativo").setContentText("Este celular pode receber comandos autorizados do seu PC").setContentIntent(open).setOngoing(true).build()
    }

    private fun poll(config: Config) {
      runCatching {
        val data = request(config, "/api/remote/poll", JSONObject().put("device_id", deviceId(this))) ?: return@runCatching
        val commands = data.optJSONArray("commands") ?: return@runCatching
        for (index in 0 until commands.length()) {
            val command = commands.optJSONObject(index) ?: continue
            val result = execute(this, command.optString("command"))
            request(config, "/api/remote/result", JSONObject().put("device_id", deviceId(this)).put("command_id", command.optString("id")).put("ok", result.first).put("result", result.second))
        }
      }
    }

    data class Config(val origin: String, val token: String)

    companion object {
        private const val CHANNEL = "jarvis_remote_control"
        private const val ID = 91
        private const val STOP = "com.example.jarvismobile.STOP_REMOTE_CONTROL"

        fun start(context: Context) = context.startForegroundService(Intent(context, RemoteControlService::class.java))
        fun stop(context: Context) = context.startService(Intent(context, RemoteControlService::class.java).setAction(STOP))
        fun isEnabled(context: Context) = context.getSharedPreferences("jarvis_remote", Context.MODE_PRIVATE).getBoolean("enabled", false)
        fun setEnabled(context: Context, enabled: Boolean) { context.getSharedPreferences("jarvis_remote", Context.MODE_PRIVATE).edit().putBoolean("enabled", enabled).apply(); if (enabled) start(context) else stop(context) }

        fun pairCode(context: Context, callback: (String) -> Unit) {
            val config = readConfig(context) ?: return callback("Abra o painel novamente para concluir a configuração.")
            Executors.newSingleThreadExecutor().execute {
                val data = request(config, "/api/remote/pair-code", JSONObject().put("device_id", deviceId(context)))
                callback(data?.optString("code")?.takeIf { it.isNotBlank() } ?: "Não foi possível gerar o código.")
            }
        }

        fun execute(context: Context, command: String): Pair<Boolean, String> = when (command) {
            "open_youtube" -> open(context, "com.google.android.youtube", "YouTube")
            "open_chrome" -> open(context, "com.android.chrome", "Chrome")
            "open_whatsapp" -> open(context, "com.whatsapp", "WhatsApp")
            "open_settings" -> runCatching { context.startActivity(Intent(android.provider.Settings.ACTION_SETTINGS).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)); true }.getOrDefault(false) to "Configurações"
            "home", "back", "recents", "notifications" -> {
                val done = JarvisAccessibilityService.perform(command)
                done to if (done) "Ação executada" else "Ative o serviço Acessibilidade do Jarvis nas configurações do Android."
            }
            else -> false to "Comando não permitido."
        }

        private fun open(context: Context, packageName: String, name: String): Pair<Boolean, String> {
            val launched = runCatching {
                val intent = context.packageManager.getLaunchIntentForPackage(packageName) ?: throw IllegalStateException()
                context.startActivity(intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)); true
            }.getOrDefault(false)
            return launched to if (launched) "$name aberto" else "$name não está instalado neste celular."
        }

        private fun deviceId(context: Context): String {
            val prefs = context.getSharedPreferences("jarvis_remote", Context.MODE_PRIVATE)
            return prefs.getString("device_id", null) ?: "android-" + java.util.UUID.randomUUID().toString().also { prefs.edit().putString("device_id", "android-$it").apply() }
        }

        private fun readConfig(context: Context): Config? = runCatching {
            val json = JSONObject(File(context.filesDir, "panel.json").readText())
            Config(json.getString("origin").removeSuffix("/"), json.getString("token"))
        }.getOrNull()

        private fun request(config: Config, path: String, payload: JSONObject): JSONObject? = runCatching {
            val connection = (URL(config.origin + path).openConnection() as HttpURLConnection).apply {
                requestMethod = "POST"; connectTimeout = 8_000; readTimeout = 10_000; doOutput = true
                setRequestProperty("Content-Type", "application/json")
                setRequestProperty("Cookie", "__Host-jarvis_cloud=${config.token}")
            }
            connection.outputStream.bufferedWriter().use { it.write(payload.toString()) }
            val stream = if (connection.responseCode in 200..299) connection.inputStream else connection.errorStream
            val text = stream?.bufferedReader()?.use { it.readText() }.orEmpty()
            connection.disconnect(); JSONObject(text)
        }.getOrNull()
    }
}
