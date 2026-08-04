import { FormEvent, type RefObject } from 'react'
import { BentoCard } from '../components/BentoCard'
import { GlowCard } from '../components/GlowCard'
import { SpotlightCard } from '../components/SpotlightCard'
import { AnimatedProgressCard } from '../components/AnimatedProgressCard'
import { CheckCircle2 } from 'lucide-react'
import type { Dashboard, Finance, Proactive, Tray, TtsSettings } from '../types'

type DashboardPageProps = {
  dashboard: Dashboard | null
  finance: Finance | null
  ttsSettings: TtsSettings | null
  proactive: Proactive | null
  tray: Tray | null
  taskTitle: string
  taskInputRef?: RefObject<HTMLInputElement | null>
  onTaskTitleChange: (value: string) => void
  onAddTask: (event: FormEvent) => void
  onToggleTask: (taskId: string) => void
  onDeleteTask: (taskId: string) => void
}

export function DashboardPage({
  dashboard,
  finance,
  ttsSettings,
  proactive,
  tray,
  taskTitle,
  taskInputRef,
  onTaskTitleChange,
  onAddTask,
  onToggleTask,
  onDeleteTask,
}: DashboardPageProps) {
  const reminderCount = proactive?.reminders?.length ?? 0
  const completedTasks = dashboard?.tasks?.completed ?? 0
  const pendingTasks = dashboard?.tasks?.pending ?? 0
  const totalTasks = completedTasks + pendingTasks

  return (
    <section className="dashboard-bento">
      <GlowCard glowColor="purple" className="hud-widget">
        <p className="eyebrow">BRIEFING</p>
        <strong>{proactive?.config?.briefing_time || '08:00'}</strong>
        <span>{proactive?.config?.briefing_enabled ? 'Ativo diariamente' : 'Desativado'}</span>
      </GlowCard>
      <GlowCard glowColor="blue" className="hud-widget">
        <p className="eyebrow">LEMBRETES</p>
        <strong>{reminderCount}</strong>
        <span>
          {reminderCount === 1 ? '1 pendente' : `${reminderCount} pendentes`}
        </span>
      </GlowCard>
      <GlowCard glowColor="green" className="hud-widget">
        <p className="eyebrow">INICIALIZAÇÃO</p>
        <strong>{tray?.boot_enabled ? 'Ativo' : 'Off'}</strong>
        <span>Boot com Windows</span>
      </GlowCard>
      <AnimatedProgressCard
        icon={<CheckCircle2 aria-hidden="true" />}
        title="Ritmo de execução"
        label="TAREFAS CONCLUÍDAS"
        subLabel={totalTasks ? 'progresso do seu painel' : 'adicione uma tarefa para começar'}
        currentValue={completedTasks}
        maxValue={totalTasks}
      />
      <BentoCard eyebrow="TAREFAS" title="Pendentes" meta={`${dashboard?.tasks?.pending ?? 0} abertas`}>
        <strong className="stat-big">{dashboard?.tasks?.pending ?? '—'}</strong>
      </BentoCard>
      <BentoCard eyebrow="SESSÕES" title="Salvas">
        <strong className="stat-big">{dashboard?.sessions?.total ?? '—'}</strong>
      </BentoCard>
      <BentoCard eyebrow="SISTEMA" title="CPU / RAM">
        <strong className="stat-big">
          {dashboard?.system?.cpu !== undefined ? `${Math.round(dashboard.system.cpu)}%` : '—'}
        </strong>
        <span>RAM {dashboard?.system?.ram_percent ?? '—'}%</span>
      </BentoCard>
      <BentoCard eyebrow="PRÓXIMAS TAREFAS" title="Hoje" span={2}>
        <form onSubmit={onAddTask}>
          <input
            ref={taskInputRef}
            value={taskTitle}
            onChange={event => onTaskTitleChange(event.target.value)}
            placeholder="Adicionar tarefa…"
          />
          <button type="submit">Adicionar</button>
        </form>
        <div className="task-list">
          {dashboard?.tasks?.items?.length ? (
            dashboard.tasks.items.map(task => (
              <div key={task.id} className="task-row">
                <button type="button" onClick={() => onToggleTask(task.id)}>
                  <span>{task.completed ? '✓' : '○'}</span>
                  {task.title}
                </button>
                <button
                  type="button"
                  className="task-delete"
                  aria-label={`Excluir ${task.title}`}
                  onClick={() => onDeleteTask(task.id)}
                >
                  ×
                </button>
              </div>
            ))
          ) : (
            <p>Nenhuma tarefa pendente.</p>
          )}
        </div>
      </BentoCard>
      <SpotlightCard glowColor="cyan" customSize className="hud-widget">
        <p className="eyebrow">MERCADO</p>
        {finance?.ok ? (
          Object.entries(finance.currencies || {}).map(([code, value]) => (
            <p className="market-row" key={code}>
              <span>{code}</span>
              <b>R$ {value.bid?.toFixed(code === 'BTC' ? 0 : 2) ?? '—'}</b>
            </p>
          ))
        ) : (
          <p className="empty-state">Cotações indisponíveis.</p>
        )}
      </SpotlightCard>
      <BentoCard eyebrow="TIMERS" title="Ativos">
        {dashboard?.timers?.length ? (
          dashboard.timers.map((timer, index) => (
            <p className="timer-row" key={index}>
              <b>{timer.label}</b>
              <span>{timer.fire_at ? new Date(timer.fire_at).toLocaleString('pt-BR') : '—'}</span>
            </p>
          ))
        ) : (
          <p className="empty-state">Nenhum timer ativo.</p>
        )}
      </BentoCard>
      <div className="tts-status-widget">
        <p className="eyebrow">VOZ · TTS</p>
        <strong>{ttsSettings?.tts_provider === 'edge' ? 'Edge TTS (Antonio)' : 'Gemini Flash TTS'}</strong>
        <p>{ttsSettings?.tts_provider === 'gemini' ? 'Fallback: Edge TTS' : 'Provedor alternativo ativo'}</p>
      </div>
      <BentoCard eyebrow="ESTUDOS" title="Centro ENEM" span={2}>
        <p>
          <strong>{dashboard?.tutor?.due_flashcards ?? 0}</strong> flashcards · Etapa:{' '}
          {dashboard?.tutor?.stage || '—'}
        </p>
      </BentoCard>
      <BentoCard eyebrow="ATIVIDADE" title="Recente" span={3}>
        {dashboard?.activity?.length ? (
          dashboard.activity.slice(0, 6).map((entry, index) => (
            <p className="activity-row" key={`${entry.timestamp}-${index}`}>
              <span>{entry.type === 'study' ? 'Estudo' : entry.type === 'task' ? 'Tarefa' : 'Chat'}</span>
              {entry.message}
            </p>
          ))
        ) : (
          <p className="empty-state">Nenhuma atividade recente.</p>
        )}
      </BentoCard>
    </section>
  )
}
