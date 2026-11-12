import { useEffect, useRef, useState } from 'react'
import type { StudyDashboardData } from '../../types'
import type { StudyMode } from './StudyToolbar'
import { useNextDueRefresh } from '../../hooks/useNextDueRefresh'

type StudyDashboardProps = {
  dashboard: StudyDashboardData | null
  stageTitle?: string
  dueCards: number
  enemCount: number
  assessmentCount: number
  onGuidedStudy: (message: string) => void
  onOpenMode: (mode: StudyMode) => void
  onReviewVocabulary: () => void
  onRefresh: () => unknown
}

function percent(value: number, total: number) {
  return Math.min(100, Math.max(0, (value / Math.max(1, total)) * 100))
}

export function StudyDashboard(props: StudyDashboardProps) {
  const { dashboard } = props
  const xp = dashboard?.xp
  const level = dashboard?.level
  const flashcards = dashboard?.due.flashcards ?? props.dueCards
  const nextDueAt = dashboard?.due.next_due_at || null
  const nextDueMinutes = useNextDueRefresh(nextDueAt, !!nextDueAt && Date.parse(nextDueAt) > Date.now(), props.onRefresh)

  // Anima a sequência quando ela muda ou a meta do dia é batida (não no primeiro carregamento).
  const previous = useRef<{ streak: number; goalMet: boolean } | null>(null)
  const [pop, setPop] = useState(0)
  useEffect(() => {
    if (!xp) return
    const current = { streak: xp.streak, goalMet: xp.goal_met }
    const last = previous.current
    previous.current = current
    if (last && (last.streak !== current.streak || last.goalMet !== current.goalMet)) setPop(count => count + 1)
  }, [xp?.streak, xp?.goal_met])

  return (
    <>
      <p className="eyebrow">HOJE</p>
      <h2>{props.stageTitle || 'Preparação para provas'}</h2>
      <div className="study-today-stats">
        <span><b>{flashcards}</b> flashcards para revisar</span>
        {dashboard && <span><b>{dashboard.due.vocabulary}</b> palavras para revisar</span>}
        {nextDueMinutes !== null && <span>Próximo cartão em <b>{nextDueMinutes}</b> min</span>}
        <span><b>{props.enemCount}</b> questões salvas</span>
        <span><b>{props.assessmentCount}</b> simulados</span>
      </div>
      {xp && level ? (
        <div className="study-gamification">
          <div key={pop} className={`study-streak${pop ? ' study-pop' : ''}`}>
            <strong>🔥 {xp.streak} {xp.streak === 1 ? 'dia seguido' : 'dias seguidos'}</strong>
            <small>recorde {xp.best_streak}</small>
          </div>
          <div className="study-meter">
            <div className="study-meter-label">
              <span>Meta do dia</span>
              <b>{xp.daily_xp}/{xp.daily_goal} XP</b>
            </div>
            <div
              className={`study-bar${xp.goal_met ? ' study-bar-done' : ''}`}
              role="progressbar"
              aria-label="Meta diária de XP"
              aria-valuemin={0}
              aria-valuemax={xp.daily_goal}
              aria-valuenow={xp.daily_xp}
            >
              <div style={{ width: `${percent(xp.daily_xp, xp.daily_goal)}%` }} />
            </div>
            {xp.goal_met && <p className="study-goal-met">Meta do dia batida!</p>}
          </div>
          <div className="study-meter">
            <div className="study-meter-label">
              <span>Nível {level.level} · {level.name}</span>
              <small>faltam {Math.max(0, level.xp_for_next - level.xp_into_level)} XP</small>
            </div>
            <div
              className="study-bar study-bar-level"
              role="progressbar"
              aria-label="Progresso do nível"
              aria-valuemin={0}
              aria-valuemax={level.xp_for_next}
              aria-valuenow={level.xp_into_level}
            >
              <div style={{ width: `${percent(level.xp_into_level, level.xp_for_next)}%` }} />
            </div>
          </div>
        </div>
      ) : (
        <p className="study-today-copy">Carregando painel…</p>
      )}
      <div className="study-today-actions">
        <button type="button" className="primary" onClick={() => props.onGuidedStudy('diagnostico: quero iniciar meu diagnóstico para provas. Faça uma pergunta curta por vez, comece perguntando minha matéria mais difícil e espere minha resposta antes de corrigir.')}>Fazer diagnóstico</button>
        <button type="button" onClick={() => props.onGuidedStudy('Quero montar uma sessão de estudo para hoje. Pergunte primeiro qual prova, matéria e tempo disponível; depois proponha a primeira atividade.')}>Estudar um tema</button>
        <button type="button" onClick={() => props.onGuidedStudy('simulado: quero um mini simulado de 5 questões. Envie uma questão por vez, espere minha resposta e, no final, dê desempenho, erros e uma revisão indicada.')}>Mini simulado</button>
        <button type="button" onClick={() => props.onOpenMode('review')}>Revisar agora</button>
        <button type="button" onClick={props.onReviewVocabulary}>Revisar vocabulário</button>
        <button type="button" onClick={() => props.onOpenMode('questions')}>Adicionar questão</button>
        <button type="button" onClick={() => props.onOpenMode('feynman')}>Explicar de volta</button>
      </div>
    </>
  )
}
