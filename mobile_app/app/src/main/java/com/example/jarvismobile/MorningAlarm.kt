package com.example.jarvismobile

import android.app.*
import android.content.*
import android.media.AudioAttributes
import android.media.MediaPlayer
import android.os.*
import android.view.Gravity
import android.widget.*


private const val CHANNEL = "morning_alarm"
private const val FLAGS = PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT
internal fun settings(c: Context) = c.getSharedPreferences("routine_settings", Context.MODE_PRIVATE)

private val clockTime = Regex("([01][0-9]|2[0-3]):[0-5][0-9]")

internal fun week(c: Context): List<String> {
    val prefs = settings(c)
    val stored = prefs.getString("week", null)
    return stored?.split('|') ?: List(7) { prefs.getString("alarm", "").orEmpty() }
}

// Monday is index zero. LocalDate.atTime respects each selected date across clock changes.
internal fun nextAlarm(times: List<String>, now: java.time.ZonedDateTime = java.time.ZonedDateTime.now()): Long {
    require(times.size == 7 && times.all { it.isEmpty() || clockTime.matches(it) })
    for (offset in 0L..7L) {
        val day = now.toLocalDate().plusDays(offset)
        val time = times[day.dayOfWeek.value - 1]
        if (time.isEmpty()) continue
        val at = day.atTime(java.time.LocalTime.parse(time)).atZone(now.zone)
        if (at.isAfter(now)) return at.toInstant().toEpochMilli()
    }
    return 0L
}

internal fun schedule(c: Context, times: List<String>, snooze: Long = settings(c).getLong("snooze", 0L)) {
    val alarms = c.getSystemService(AlarmManager::class.java)
    val show = PendingIntent.getActivity(c, 1, Intent(c, RoutineActivity::class.java), FLAGS)
    val daily = nextAlarm(times)
    val next = listOf(daily, snooze).filter { it > System.currentTimeMillis() }.minOrNull()
    val fire = PendingIntent.getForegroundService(c, 1, Intent(c, RingService::class.java).setAction("daily"), FLAGS)
    if (next == null) alarms.cancel(fire)
    else alarms.setAlarmClock(AlarmManager.AlarmClockInfo(next, show), fire)
    settings(c).edit().putLong("next", next ?: 0L).apply()
}

class AlarmReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        try { schedule(context, week(context)) } catch (_: SecurityException) {
            settings(context).edit().remove("next").apply()
        }
    }
}

internal fun alarmAudio(c: Context, id: Int): MediaPlayer {
    return MediaPlayer().apply {
        setAudioAttributes(AudioAttributes.Builder().setUsage(AudioAttributes.USAGE_ALARM)
            .setContentType(AudioAttributes.CONTENT_TYPE_MUSIC).build())
        c.resources.openRawResourceFd(id).use { setDataSource(it.fileDescriptor, it.startOffset, it.length) }
        prepare()
    }
}

class RingService : Service() {
    private var player: MediaPlayer? = null
    private val handler = Handler(Looper.getMainLooper())
    override fun onBind(intent: Intent?) = null
    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        val manager = getSystemService(NotificationManager::class.java)
        manager.createNotificationChannel(NotificationChannel(CHANNEL, "Despertador Jarvis", NotificationManager.IMPORTANCE_HIGH).apply {
            setSound(null, null)
            lockscreenVisibility = Notification.VISIBILITY_PUBLIC
        })
        val wake = PendingIntent.getActivity(this, 2, Intent(this, WakeActivity::class.java), FLAGS)
        startForeground(72, Notification.Builder(this, CHANNEL).setSmallIcon(android.R.drawable.ic_lock_idle_alarm)
            .setContentTitle("Bom dia!").setContentText("Toque para confirmar que acordou.")
            .setCategory(Notification.CATEGORY_ALARM).setOngoing(true).setContentIntent(wake)
            .setFullScreenIntent(wake, true).build())
        if (intent?.action == "daily") {
            val prefs = settings(this)
            val snooze = prefs.getLong("snooze", 0L)
            val times = week(this)
            if (times.all { it.isEmpty() } && snooze == 0L) { stopSelf(); return START_NOT_STICKY }
            if (snooze <= System.currentTimeMillis() + 1000) prefs.edit().remove("snooze").apply()
            try { schedule(this, times) } catch (_: SecurityException) { prefs.edit().remove("next").apply() }
        }
        if (player == null) {
            player = alarmAudio(this, R.raw.bom_dia).apply {
                setWakeMode(this@RingService, PowerManager.PARTIAL_WAKE_LOCK)
                isLooping = true
                start()
            }
            settings(this).edit().putBoolean("ringing", true).apply()
            handler.postDelayed({ stopSelf() }, 10 * 60_000L)
        }
        return START_NOT_STICKY
    }
    override fun onDestroy() {
        handler.removeCallbacksAndMessages(null)
        player?.release()
        settings(this).edit().putBoolean("ringing", false).apply()
        super.onDestroy()
    }
}

class WakeActivity : Activity() {
    override fun onCreate(state: Bundle?) {
        super.onCreate(state)
        @Suppress("DEPRECATION")
        window.addFlags(android.view.WindowManager.LayoutParams.FLAG_SHOW_WHEN_LOCKED or
            android.view.WindowManager.LayoutParams.FLAG_TURN_SCREEN_ON or android.view.WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        setContentView(LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            gravity = Gravity.CENTER
            setBackgroundColor(0xff102026.toInt())
            addView(TextView(context).apply { text = "Bom dia!"; textSize = 42f; setTextColor(-1) })
            addView(Button(context).apply {
                text = "Acordei"
                setOnClickListener {
                    stopService(Intent(context, RingService::class.java))
                    startActivity(Intent(context, RoutineActivity::class.java).setAction("morning")
                        .addFlags(Intent.FLAG_ACTIVITY_CLEAR_TOP or Intent.FLAG_ACTIVITY_SINGLE_TOP))
                    finish()
                }
            })
            addView(Button(context).apply {
                text = "Adiar 5 min"
                setOnClickListener {
                    val until = System.currentTimeMillis() + 300_000L
                    try {
                        schedule(context, week(context), until)
                        settings(context).edit().putLong("snooze", until).apply()
                        stopService(Intent(context, RingService::class.java))
                        finish()
                    } catch (_: SecurityException) {
                        Toast.makeText(context, "Autorize alarmes exatos para adiar.", Toast.LENGTH_LONG).show()
                    }
                }
            })
        })
    }
}

