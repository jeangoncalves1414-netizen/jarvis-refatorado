package com.example.jarvismobile

import java.time.ZonedDateTime
import org.junit.Assert.assertEquals
import org.junit.Test

class WeekAlarmTest {
    @Test fun skipsDisabledDaysAndWrapsToNextWeek() {
        val monday = ZonedDateTime.parse("2026-11-16T07:00:00-03:00")
        val times = listOf("07:00", "", "", "", "", "08:30", "")
        assertEquals(monday.plusDays(5).withHour(8).withMinute(30).toInstant().toEpochMilli(), nextAlarm(times, monday))
        assertEquals(monday.plusWeeks(1).toInstant().toEpochMilli(), nextAlarm(times, monday.plusDays(6)))
        assertEquals(0L, nextAlarm(List(7) { "" }, monday))
    }
}

