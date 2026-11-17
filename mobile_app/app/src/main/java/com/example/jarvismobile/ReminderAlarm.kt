package com.example.jarvismobile

import android.app.AlarmManager
import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.os.Build

private const val REMINDER_CHANNEL = "jarvis_reminders"
private const val REMINDER_ACTION = "com.example.jarvismobile.REMINDER"

internal fun scheduleReminder(context: Context, id: String, message: String, at: Long) {
    if (at <= System.currentTimeMillis()) return
    val intent = Intent(context, ReminderReceiver::class.java).setAction(REMINDER_ACTION)
        .putExtra("id", id).putExtra("message", message)
    val pending = PendingIntent.getBroadcast(context, id.hashCode(), intent,
        PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT)
    val alarms = context.getSystemService(AlarmManager::class.java)
    try {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S && alarms.canScheduleExactAlarms()) {
            alarms.setExactAndAllowWhileIdle(AlarmManager.RTC_WAKEUP, at, pending)
        } else alarms.setAndAllowWhileIdle(AlarmManager.RTC_WAKEUP, at, pending)
    } catch (_: SecurityException) {
        alarms.setAndAllowWhileIdle(AlarmManager.RTC_WAKEUP, at, pending)
    }
}

internal fun cancelReminder(context: Context, id: String) {
    val intent = Intent(context, ReminderReceiver::class.java).setAction(REMINDER_ACTION)
    val pending = PendingIntent.getBroadcast(context, id.hashCode(), intent, PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT)
    context.getSystemService(AlarmManager::class.java).cancel(pending)
    pending.cancel()
}

class ReminderReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        val manager = context.getSystemService(NotificationManager::class.java)
        manager.createNotificationChannel(NotificationChannel(REMINDER_CHANNEL, "Lembretes Jarvis", NotificationManager.IMPORTANCE_HIGH))
        val open = PendingIntent.getActivity(context, intent.getStringExtra("id")?.hashCode() ?: 0,
            Intent(context, PanelActivity::class.java), PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT)
        val notification = Notification.Builder(context, REMINDER_CHANNEL)
            .setSmallIcon(android.R.drawable.ic_lock_idle_alarm)
            .setContentTitle("Lembrete do Jarvis")
            .setContentText(intent.getStringExtra("message") ?: "Você tem um lembrete.")
            .setContentIntent(open).setAutoCancel(true).setCategory(Notification.CATEGORY_REMINDER).build()
        manager.notify(intent.getStringExtra("id")?.hashCode() ?: System.currentTimeMillis().toInt(), notification)
    }
}
