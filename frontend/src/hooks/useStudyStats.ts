import { useEffect, useState } from 'react'
import type { StudyDashboardData, StudyStatsData } from '../types'

type SetNotice = (message: string) => void

// Mesmos limites do backend (app/storage/study_xp.py POMODORO_MIN/MAX_MINUTES).
const POMODORO_MIN_MINUTES = 5
const POMODORO_MAX_MINUTES = 90

async function readOkJson(result: PromiseSettledResult<Response>) {
  if (result.status !== 'fulfilled' || !result.value.ok) return null
  try {
    return await result.value.json()
  } catch {
    return null
  }
}

export function useStudyStats(setNotice: SetNotice) {
  const [dashboard, setDashboard] = useState<StudyDashboardData | null>(null)
  const [stats, setStats] = useState<StudyStatsData | null>(null)

  const refresh = async () => {
    const results = await Promise.allSettled([fetch('/api/study/dashboard'), fetch('/api/study/stats')])
    const [dashboardData, statsData] = await Promise.all(results.map(readOkJson))
    if (dashboardData) setDashboard(dashboardData as StudyDashboardData)
    if (statsData) setStats(statsData as StudyStatsData)
  }

  const awardPomodoro = async (minutes: number) => {
    if (minutes < POMODORO_MIN_MINUTES) {
      setNotice(`Pomodoro concluído! Blocos com menos de ${POMODORO_MIN_MINUTES} min não valem XP.`)
      return
    }
    const response = await fetch('/api/study/pomodoro', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ minutes: Math.min(POMODORO_MAX_MINUTES, Math.round(minutes)) }),
    }).catch(() => null)
    if (!response?.ok) {
      setNotice('Não foi possível registrar o Pomodoro.')
      return
    }
    setNotice('Pomodoro concluído! +20 XP')
    refresh().catch(() => undefined)
  }

  useEffect(() => {
    refresh().catch(() => undefined)
  }, [])

  return { dashboard, stats, refresh, awardPomodoro }
}
