package com.example.jarvismobile

import android.app.job.JobInfo
import android.app.job.JobParameters
import android.app.job.JobScheduler
import android.app.job.JobService
import android.content.ComponentName
import android.content.Context
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.net.HttpURLConnection
import java.net.URL
import java.time.Instant
import java.util.concurrent.Executors

/** Reinstates cloud reminders after an Android restart or a reminder made on the PC. */
internal object CloudReminderSync {
    private const val JOB_ID = 508
    private const val COOKIE = "__Host-jarvis_cloud"
    private val worker = Executors.newSingleThreadExecutor()

    fun setup(context: Context) {
        val scheduler = context.getSystemService(JobScheduler::class.java)
        scheduler.schedule(
            JobInfo.Builder(JOB_ID, ComponentName(context, CloudReminderSyncJob::class.java))
                .setRequiredNetworkType(JobInfo.NETWORK_TYPE_ANY)
                .setPersisted(true)
                .setPeriodic(15 * 60_000L)
                .build()
        )
    }

    fun start(context: Context, finished: () -> Unit = {}) {
        val app = context.applicationContext
        worker.execute {
            try { sync(app) } finally { finished() }
        }
    }

    private fun sync(context: Context) {
        if (context.getString(R.string.panel_mode) != "cloud") return
        val config = runCatching { JSONObject(File(context.filesDir, "panel.json").readText()) }.getOrNull() ?: return
        val origin = config.optString("origin").trim().removeSuffix("/")
        val token = config.optString("token").trim()
        if (!origin.startsWith("https://") || !Regex("[a-zA-Z0-9_-]{40,100}").matches(token)) return
        scheduleProactive(context, getJson("$origin/api/proactive", token).optJSONArray("reminders") ?: JSONArray())
        scheduleCalendar(context, getJson("$origin/api/calendar", token).optJSONArray("events") ?: JSONArray())
    }

    private fun getJson(url: String, token: String): JSONObject {
        val connection = URL(url).openConnection() as HttpURLConnection
        return try {
            connection.connectTimeout = 5_000
            connection.readTimeout = 10_000
            connection.instanceFollowRedirects = false
            connection.setRequestProperty("Cookie", "$COOKIE=$token")
            if (connection.responseCode != HttpURLConnection.HTTP_OK) return JSONObject()
            JSONObject(connection.inputStream.bufferedReader().use { it.readText() })
        } catch (_: Exception) { JSONObject() }
        finally { connection.disconnect() }
    }

    private fun scheduleProactive(context: Context, reminders: JSONArray) {
        for (index in 0 until reminders.length()) {
            val reminder = reminders.optJSONObject(index) ?: continue
            val id = reminder.optString("id")
            val message = reminder.optString("message")
            val at = instant(reminder.optString("target_time"))
            if (id.isNotBlank() && message.isNotBlank() && at != null) scheduleReminder(context, id, message, at)
        }
    }

    private fun scheduleCalendar(context: Context, events: JSONArray) {
        for (index in 0 until events.length()) {
            val event = events.optJSONObject(index) ?: continue
            val id = event.optString("id")
            if (id.isBlank()) continue
            if (event.optString("reminder_status") == "cancelled") {
                cancelReminder(context, id)
                continue
            }
            val at = instant(event.optString("reminder_at"))
            val title = event.optString("title")
            if (at != null && title.isNotBlank()) scheduleReminder(context, id, "Calendário: $title", at)
        }
    }

    private fun instant(value: String): Long? = runCatching { Instant.parse(value).toEpochMilli() }.getOrNull()
}

class CloudReminderSyncJob : JobService() {
    override fun onStartJob(params: JobParameters): Boolean {
        CloudReminderSync.start(this) { jobFinished(params, false) }
        return true
    }

    override fun onStopJob(params: JobParameters) = true
}
