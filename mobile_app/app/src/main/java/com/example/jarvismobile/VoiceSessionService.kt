package com.example.jarvismobile

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.content.pm.ServiceInfo
import android.os.Build
import android.os.IBinder

class VoiceSessionService : Service() {
    override fun onBind(intent: Intent?): IBinder? = null

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        if (intent?.action == STOP) {
            stopForeground(STOP_FOREGROUND_REMOVE)
            stopSelf()
            return START_NOT_STICKY
        }
        val manager = getSystemService(NotificationManager::class.java)
        manager.createNotificationChannel(NotificationChannel(CHANNEL, "Ligação Jarvis", NotificationManager.IMPORTANCE_LOW).apply {
            setSound(null, null)
            setShowBadge(false)
        })
        val openPanel = PendingIntent.getActivity(this, 81, Intent(this, PanelActivity::class.java),
            PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT)
        val notification = Notification.Builder(this, CHANNEL)
            .setSmallIcon(android.R.drawable.ic_btn_speak_now)
            .setContentTitle("Jarvis em ligação")
            .setContentText("Ouvindo em segundo plano")
            .setContentIntent(openPanel)
            .setOngoing(true)
            .setCategory(Notification.CATEGORY_SERVICE)
            .build()
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            startForeground(ID, notification, ServiceInfo.FOREGROUND_SERVICE_TYPE_MICROPHONE)
        } else startForeground(ID, notification)
        return START_NOT_STICKY
    }

    override fun onTaskRemoved(rootIntent: Intent?) {
        stopSelf()
    }

    companion object {
        private const val CHANNEL = "jarvis_voice_session"
        private const val ID = 83
        private const val STOP = "com.example.jarvismobile.STOP_VOICE_SESSION"

        fun start(context: Context) {
            context.startForegroundService(Intent(context, VoiceSessionService::class.java))
        }

        fun stop(context: Context) {
            context.startService(Intent(context, VoiceSessionService::class.java).setAction(STOP))
        }
    }
}
