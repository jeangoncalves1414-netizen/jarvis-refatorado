package com.example.jarvismobile

import android.app.job.*
import android.content.ComponentName
import android.content.Context
import android.net.ConnectivityManager
import android.net.NetworkCapabilities
import android.util.Base64
import java.net.URL
import java.security.KeyStore
import java.security.cert.CertificateFactory
import java.util.concurrent.Executors
import javax.net.ssl.*
import org.json.JSONObject

internal object WifiRoutine {
    private val worker = Executors.newSingleThreadExecutor()
    fun status(c: Context): String = settings(c).getString("wifiStatus", null) ?: "Pareamento inicial por USB necessário."

    fun setup(c: Context) {
        val scheduler = c.getSystemService(JobScheduler::class.java)
        scheduler.schedule(JobInfo.Builder(507, ComponentName(c, RoutineSyncJob::class.java))
            .setRequiredNetworkType(JobInfo.NETWORK_TYPE_UNMETERED).setPeriodic(15 * 60_000L).setPersisted(true).build())
    }

    fun start(context: Context, finished: () -> Unit = {}) {
        val c = context.applicationContext
        worker.execute {
            try {
                val prefs = settings(c)
                val pair = prefs.getString("wifiPair", null) ?: return@execute
                val network = c.getSystemService(ConnectivityManager::class.java)
                if (network.getNetworkCapabilities(network.activeNetwork)?.hasTransport(NetworkCapabilities.TRANSPORT_WIFI) != true) {
                    prefs.edit().putString("wifiStatus", "Aguardando Wi-Fi.").apply()
                    return@execute
                }
                val before = JSONObject(RoutineStore.read(c))
                val cfg = JSONObject(pair)
                val cert = CertificateFactory.getInstance("X.509").generateCertificate(
                    Base64.decode(cfg.getString("cert"), Base64.DEFAULT).inputStream())
                val trust = KeyStore.getInstance(KeyStore.getDefaultType()).apply {
                    load(null); setCertificateEntry("paired", cert)
                }
                val tm = TrustManagerFactory.getInstance(TrustManagerFactory.getDefaultAlgorithm()).apply { init(trust) }
                val tls = SSLContext.getInstance("TLS").apply { init(null, tm.trustManagers, null) }
                val conn = URL(cfg.getString("url")).openConnection() as HttpsURLConnection
                try {
                    conn.sslSocketFactory = tls.socketFactory
                    conn.connectTimeout = 4000
                    conn.readTimeout = 10000
                    conn.instanceFollowRedirects = false
                    conn.requestMethod = "POST"
                    conn.doOutput = true
                    conn.setRequestProperty("Authorization", "Bearer " + cfg.getString("token"))
                    conn.setRequestProperty("Content-Type", "application/json")
                    val payload = JSONObject().put("rev",before.getLong("rev")).put("queue",before.getJSONArray("queue"))
                    conn.outputStream.use { it.write(payload.toString().toByteArray()) }
                    val msg = when(conn.responseCode) {
                        200 -> {
                            val saved = RoutineStore.save(c, conn.inputStream.bufferedReader().use { it.readText() })
                            if (saved) "Sincronizado por Wi-Fi." else "Nova edição no celular. Sincronize novamente."
                        }
                        409 -> {
                            val conflict = JSONObject(conn.errorStream.bufferedReader().use { it.readText() })
                            before.put("conflict",conflict)
                            RoutineStore.save(c,before.toString())
                            "Escolha a versão para resolver o conflito."
                        }
                        else -> "O PC recusou a sincronização. Verifique o pareamento."
                    }
                    prefs.edit().putString("wifiStatus",msg).apply()
                } finally { conn.disconnect() }
            } catch (_: Exception) {
                settings(c).edit().putString("wifiStatus","PC indisponível. Alterações guardadas no celular.").apply()
            } finally { finished() }
        }
    }
}

class RoutineSyncJob : JobService() {
    override fun onStartJob(params: JobParameters): Boolean {
        WifiRoutine.start(this) { jobFinished(params,false) }
        return true
    }
    override fun onStopJob(params: JobParameters) = true
}

