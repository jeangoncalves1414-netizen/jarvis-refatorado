import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  AlertTriangle,
  Bell,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  Clock,
  ExternalLink,
  History,
  Mic,
  Play,
  Plus,
  Terminal,
  Trash2,
  XCircle,
} from 'lucide-react'
import { ConfirmDialog } from '../components/ConfirmDialog'
import { panelRequest } from '../utils/panelApi'
import type { RoutinesWindowParams, WindowComponentProps } from './registry'

type RoutineTrigger =
  | { type: 'at'; datetime: string }
  | { type: 'daily'; time: string }
  | { type: 'weekdays'; time: string }
  | { type: 'weekly'; days: string[]; time: string }
  | { type: 'interval'; minutes: number }
  | { type: 'voice'; phrase: string }
  | { type: 'command'; slash: string }
  | {
    type: 'event'
    event: string
    params?: Record<string, unknown>
    mode?: 'alert' | 'run'
    cooldown_minutes?: number
    window?: { start: string; end: string }
  }

type RoutineStep = {
  id: string
  label: string
  tool: string
  operation: string
  params: Record<string, unknown>
  delay_before: number
  on_failure: 'stop' | 'continue' | 'retry'
  retries: number
  timeout: number | null
}

type Routine = {
  id: string
  name: string
  enabled: boolean
  steps: RoutineStep[]
  triggers: RoutineTrigger[]
  quiet: { start: string; end: string } | null
  catch_up_minutes: number
  created_at: number
  updated_at: number
  last_scheduled_for?: number | null
  last_run_at?: number | null
  last_status?: string | null
  last_run_id?: string | null
  last_summary?: string | null
  running?: boolean
  next_run?: string | null
  next_run_label?: string
  trigger_labels?: string[]
}

type RoutineRun = {
  id: string
  routine_id: string
  run_id?: string | null
  trigger_kind: string
  scheduled_for?: number | null
  started_at: number
  finished_at?: number | null
  status: string
  step_index: number
  summary: string
}

type ToolMeta = {
  tool: string
  label: string
  operation_argument: string
  operations: { name: string; risk: string }[]
  risk: string
  params: Record<string, { type: string; description: string; enum?: string[] }>
}

const WEEKDAYS = [
  { id: 'mon', label: 'Seg' },
  { id: 'tue', label: 'Ter' },
  { id: 'wed', label: 'Qua' },
  { id: 'thu', label: 'Qui' },
  { id: 'fri', label: 'Sex' },
  { id: 'sat', label: 'Sáb' },
  { id: 'sun', label: 'Dom' },
]

function formatTimestamp(stamp?: number | null) {
  if (!stamp) return '—'
  const date = new Date(stamp * 1000)
  return date.toLocaleString('pt-BR', { dateStyle: 'short', timeStyle: 'short' })
}

function statusColor(status?: string | null) {
  switch (status) {
    case 'succeeded':
      return 'var(--ws-ok)'
    case 'failed':
      return 'var(--ws-danger)'
    case 'running':
      return 'var(--ws-accent)'
    case 'paused':
    case 'alert':
      return 'var(--ws-warn)'
    default:
      return 'var(--ws-muted)'
  }
}

function blankStep(index: number, metaList: ToolMeta[]): RoutineStep {
  const defaultMeta = metaList[0]
  const defaultOp = defaultMeta?.operations[0]?.name || ''
  return {
    id: `s${index + 1}`,
    label: defaultMeta ? `Passo ${index + 1}` : 'Nova etapa',
    tool: defaultMeta?.tool || 'open_windows_app',
    operation: defaultOp,
    params: {},
    delay_before: 0,
    on_failure: 'stop',
    retries: 0,
    timeout: null,
  }
}

export function RoutinesWindow({ params, openRun }: WindowComponentProps<RoutinesWindowParams>) {
  const [routines, setRoutines] = useState<Routine[]>([])
  const [toolsMeta, setToolsMeta] = useState<ToolMeta[]>([])
  const [alerts, setAlerts] = useState<RoutineRun[]>([])
  const [selectedId, setSelectedId] = useState<string | null>(params.routine_id || null)
  const [isCreating, setIsCreating] = useState(false)
  const [activeTab, setActiveTab] = useState<'routines' | 'alerts'>('routines')
  const [detailTab, setDetailTab] = useState<'editor' | 'history'>('editor')

  // Estado do formulário de edição
  const [formName, setFormName] = useState('')
  const [formEnabled, setFormEnabled] = useState(true)
  const [formCatchUp, setFormCatchUp] = useState(15)
  const [formQuietEnabled, setFormQuietEnabled] = useState(false)
  const [formQuietStart, setFormQuietStart] = useState('22:00')
  const [formQuietEnd, setFormQuietEnd] = useState('07:00')

  // Gatilho de horário
  const [scheduleType, setScheduleType] = useState<'none' | 'at' | 'daily' | 'weekdays' | 'weekly' | 'interval'>('none')
  const [scheduleTime, setScheduleTime] = useState('08:00')
  const [scheduleDate, setScheduleDate] = useState('')
  const [scheduleDays, setScheduleDays] = useState<string[]>(['mon', 'wed', 'fri'])
  const [scheduleInterval, setScheduleInterval] = useState(30)

  // Gatilho de voz e comando
  const [voicePhrase, setVoicePhrase] = useState('')
  const [commandSlash, setCommandSlash] = useState('')

  // Gatilho de evento
  const [eventEnabled, setEventEnabled] = useState(false)
  const [eventType, setEventType] = useState('resource')
  const [eventMetric, setEventMetric] = useState('cpu')
  const [eventThreshold, setEventThreshold] = useState(90)
  const [eventForSeconds, setEventForSeconds] = useState(120)
  const [eventAppName, setEventAppName] = useState('')
  const [eventMinutes, setEventMinutes] = useState(15)
  const [eventMode, setEventMode] = useState<'alert' | 'run'>('alert')
  const [eventCooldown, setEventCooldown] = useState(30)

  // Etapas
  const [steps, setSteps] = useState<RoutineStep[]>([])

  // Histórico da rotina selecionada
  const [history, setHistory] = useState<RoutineRun[]>([])

  // Feedback e confirmação
  const [statusMsg, setStatusMsg] = useState('')
  const [errorMsg, setErrorMsg] = useState('')
  const [saving, setSaving] = useState(false)
  const [runningRoutineId, setRunningRoutineId] = useState<string | null>(null)
  const [pendingDeleteId, setPendingDeleteId] = useState<string | null>(null)

  // Carrega rotinas e metadados de ferramentas
  const loadRoutines = useCallback(async () => {
    try {
      const res = await panelRequest('/api/routines') as { ok?: boolean; routines?: Routine[] }
      if (res?.ok && Array.isArray(res.routines)) {
        setRoutines(res.routines)
      }
    } catch {
      /* ignore fetch error */
    }
  }, [])

  const loadMeta = useCallback(async () => {
    try {
      const res = await panelRequest('/api/routines/meta') as { ok?: boolean; tools?: ToolMeta[] }
      if (res?.ok && Array.isArray(res.tools)) {
        setToolsMeta(res.tools)
      }
    } catch {
      /* ignore fetch error */
    }
  }, [])

  const loadAlerts = useCallback(async () => {
    try {
      const res = await panelRequest('/api/routines/alerts?limit=50') as { ok?: boolean; alerts?: RoutineRun[] }
      if (res?.ok && Array.isArray(res.alerts)) {
        setAlerts(res.alerts)
      }
    } catch {
      /* ignore fetch error */
    }
  }, [])

  const loadHistory = useCallback(async (id: string) => {
    try {
      const res = await panelRequest(`/api/routines/${encodeURIComponent(id)}`) as { ok?: boolean; routine?: Routine; history?: RoutineRun[] }
      if (res?.ok && Array.isArray(res.history)) {
        setHistory(res.history)
      }
    } catch {
      /* ignore fetch error */
    }
  }, [])

  useEffect(() => {
    void loadRoutines()
    void loadMeta()
    void loadAlerts()

    const onRoutineEvent = () => {
      void loadRoutines()
      void loadAlerts()
      if (selectedId) void loadHistory(selectedId)
    }

    window.addEventListener('jarvis:routine-event', onRoutineEvent)
    return () => window.removeEventListener('jarvis:routine-event', onRoutineEvent)
  }, [loadRoutines, loadMeta, loadAlerts, loadHistory, selectedId])

  // Preenche o formulário ao selecionar uma rotina
  useEffect(() => {
    setErrorMsg('')
    setStatusMsg('')
    if (isCreating) {
      setFormName('Nova rotina')
      setFormEnabled(true)
      setFormCatchUp(15)
      setFormQuietEnabled(false)
      setFormQuietStart('22:00')
      setFormQuietEnd('07:00')
      setScheduleType('none')
      setScheduleTime('08:00')
      setScheduleDate('')
      setScheduleDays(['mon', 'wed', 'fri'])
      setScheduleInterval(30)
      setVoicePhrase('')
      setCommandSlash('')
      setEventEnabled(false)
      setSteps(toolsMeta.length ? [blankStep(0, toolsMeta)] : [])
      setHistory([])
      return
    }

    if (!selectedId) {
      if (routines.length > 0) setSelectedId(routines[0].id)
      return
    }

    const current = routines.find(r => r.id === selectedId)
    if (!current) return

    setFormName(current.name)
    setFormEnabled(current.enabled)
    setFormCatchUp(current.catch_up_minutes ?? 15)
    if (current.quiet) {
      setFormQuietEnabled(true)
      setFormQuietStart(current.quiet.start || '22:00')
      setFormQuietEnd(current.quiet.end || '07:00')
    } else {
      setFormQuietEnabled(false)
    }

    // Identifica gatilhos
    let sched: RoutineTrigger | undefined
    let voice: string = ''
    let slash: string = ''
    let ev: Extract<RoutineTrigger, { type: 'event' }> | undefined

    for (const t of current.triggers || []) {
      if (['at', 'daily', 'weekdays', 'weekly', 'interval'].includes(t.type)) {
        sched = t
      } else if (t.type === 'voice') {
        voice = t.phrase
      } else if (t.type === 'command') {
        slash = t.slash
      } else if (t.type === 'event') {
        ev = t
      }
    }

    if (sched) {
      if (sched.type === 'at') {
        setScheduleType('at')
        setScheduleDate(sched.datetime)
      } else if (sched.type === 'daily') {
        setScheduleType('daily')
        setScheduleTime(sched.time)
      } else if (sched.type === 'weekdays') {
        setScheduleType('weekdays')
        setScheduleTime(sched.time)
      } else if (sched.type === 'weekly') {
        setScheduleType('weekly')
        setScheduleTime(sched.time)
        setScheduleDays(sched.days || [])
      } else if (sched.type === 'interval') {
        setScheduleType('interval')
        setScheduleInterval(sched.minutes)
      }
    } else {
      setScheduleType('none')
    }

    setVoicePhrase(voice)
    setCommandSlash(slash)

    if (ev) {
      setEventEnabled(true)
      setEventType(ev.event || 'resource')
      setEventMode(ev.mode || 'alert')
      setEventCooldown(ev.cooldown_minutes ?? 30)
      const p = ev.params || {}
      if (ev.event === 'resource') {
        setEventMetric(String(p.metric || 'cpu'))
        setEventThreshold(Number(p.threshold || 90))
        setEventForSeconds(Number(p.for_seconds || 120))
      } else if (ev.event === 'app_started' || ev.event === 'app_closed') {
        setEventAppName(String(p.app_name || ''))
      } else if (ev.event === 'calendar_before' || ev.event === 'idle' || ev.event === 'returned') {
        setEventMinutes(Number(p.minutes || 15))
      }
    } else {
      setEventEnabled(false)
    }

    setSteps(current.steps || [])
    void loadHistory(current.id)
  }, [selectedId, isCreating, routines, toolsMeta, loadHistory])

  // Salvar
  const handleSave = async () => {
    setErrorMsg('')
    setStatusMsg('')
    if (!formName.trim()) {
      setErrorMsg('Informe o nome da rotina.')
      return
    }

    const triggers: RoutineTrigger[] = []
    if (scheduleType === 'at' && scheduleDate) {
      triggers.push({ type: 'at', datetime: scheduleDate })
    } else if (scheduleType === 'daily' && scheduleTime) {
      triggers.push({ type: 'daily', time: scheduleTime })
    } else if (scheduleType === 'weekdays' && scheduleTime) {
      triggers.push({ type: 'weekdays', time: scheduleTime })
    } else if (scheduleType === 'weekly' && scheduleTime) {
      triggers.push({ type: 'weekly', days: scheduleDays, time: scheduleTime })
    } else if (scheduleType === 'interval' && scheduleInterval > 0) {
      triggers.push({ type: 'interval', minutes: scheduleInterval })
    }

    if (voicePhrase.trim()) {
      triggers.push({ type: 'voice', phrase: voicePhrase.trim() })
    }

    if (commandSlash.trim()) {
      triggers.push({ type: 'command', slash: commandSlash.trim().replace(/^\//, '') })
    }

    if (eventEnabled) {
      let paramsObj: Record<string, unknown> = {}
      if (eventType === 'resource') {
        paramsObj = { metric: eventMetric, threshold: eventThreshold, for_seconds: eventForSeconds }
      } else if (eventType === 'app_started' || eventType === 'app_closed') {
        paramsObj = { app_name: eventAppName.trim() }
      } else if (eventType === 'calendar_before' || eventType === 'idle' || eventType === 'returned') {
        paramsObj = { minutes: eventMinutes }
      }
      triggers.push({
        type: 'event',
        event: eventType,
        params: paramsObj,
        mode: eventMode,
        cooldown_minutes: eventCooldown,
      })
    }

    const payload = {
      name: formName.trim(),
      enabled: formEnabled,
      catch_up_minutes: formCatchUp,
      quiet: formQuietEnabled ? { start: formQuietStart, end: formQuietEnd } : null,
      triggers,
      steps: steps.map((s, idx) => ({
        ...s,
        id: `s${idx + 1}`,
        delay_before: Math.max(0, Number(s.delay_before) || 0),
        retries: s.on_failure === 'retry' ? Math.max(1, Math.min(3, Number(s.retries) || 1)) : 0,
        timeout: s.timeout ? Number(s.timeout) : null,
      })),
    }

    setSaving(true)
    try {
      if (isCreating) {
        const res = await panelRequest('/api/routines', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
        }) as { ok?: boolean; routine?: Routine; error?: string }
        if (!res?.ok || !res.routine) {
          throw new Error(res?.error || 'Erro ao criar a rotina.')
        }
        setStatusMsg('Rotina criada com sucesso.')
        setIsCreating(false)
        await loadRoutines()
        setSelectedId(res.routine.id)
      } else if (selectedId) {
        const res = await panelRequest(`/api/routines/${encodeURIComponent(selectedId)}`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
        }) as { ok?: boolean; routine?: Routine; error?: string }
        if (!res?.ok) {
          throw new Error(res?.error || 'Erro ao salvar a rotina.')
        }
        setStatusMsg('Rotina salva com sucesso.')
        await loadRoutines()
      }
    } catch (err) {
      setErrorMsg(err instanceof Error ? err.message : 'Erro ao salvar rotina.')
    } finally {
      setSaving(false)
    }
  }

  // Executar agora
  const handleRunNow = async (routineId: string) => {
    setRunningRoutineId(routineId)
    setErrorMsg('')
    setStatusMsg('')
    try {
      const res = await panelRequest(`/api/routines/${encodeURIComponent(routineId)}/run`, {
        method: 'POST',
      }) as { ok?: boolean; run_id?: string; error?: string }
      if (!res?.ok) {
        throw new Error(res?.error || 'Não foi possível executar a rotina.')
      }
      setStatusMsg('Rotina iniciada.')
      await loadRoutines()
      if (routineId === selectedId) {
        void loadHistory(routineId)
      }
    } catch (err) {
      setErrorMsg(err instanceof Error ? err.message : 'Erro ao disparar rotina.')
    } finally {
      setRunningRoutineId(null)
    }
  }

  // Alternar ativo/inativo
  const handleToggleEnable = async (routine: Routine) => {
    try {
      await panelRequest(`/api/routines/${encodeURIComponent(routine.id)}/enable`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ enabled: !routine.enabled }),
      })
      await loadRoutines()
    } catch {
      /* ignore toggle error */
    }
  }

  // Excluir
  const handleDelete = async () => {
    if (!pendingDeleteId) return
    try {
      await panelRequest(`/api/routines/${encodeURIComponent(pendingDeleteId)}/delete`, {
        method: 'POST',
      })
      setPendingDeleteId(null)
      setIsCreating(false)
      setSelectedId(null)
      await loadRoutines()
    } catch (err) {
      setErrorMsg(err instanceof Error ? err.message : 'Erro ao excluir rotina.')
    }
  }

  // Adicionar etapa
  const addStep = () => {
    if (steps.length >= 20) {
      setErrorMsg('Máximo de 20 etapas por rotina.')
      return
    }
    setSteps(prev => [...prev, blankStep(prev.length, toolsMeta)])
  }

  // Remover etapa
  const removeStep = (index: number) => {
    setSteps(prev => prev.filter((_, i) => i !== index))
  }

  // Reordenar etapas
  const moveStep = (index: number, direction: 'up' | 'down') => {
    const target = direction === 'up' ? index - 1 : index + 1
    if (target < 0 || target >= steps.length) return
    setSteps(prev => {
      const next = [...prev]
      const temp = next[index]
      next[index] = next[target]
      next[target] = temp
      return next
    })
  }

  // Atualizar etapa
  const updateStep = (index: number, patch: Partial<RoutineStep>) => {
    setSteps(prev => {
      const next = [...prev]
      next[index] = { ...next[index], ...patch }
      return next
    })
  }

  const selectedRoutine = useMemo(() => {
    return routines.find(r => r.id === selectedId)
  }, [routines, selectedId])

  return (
    <div className="ws-routines">
      {/* Coluna Esquerda: Lista e Abas */}
      <aside className="ws-routines-sidebar">
        <div className="ws-routines-sidebar-header">
          <div className="ws-routines-tabs">
            <button
              type="button"
              className={activeTab === 'routines' ? 'active' : ''}
              onClick={() => setActiveTab('routines')}
            >
              Rotinas ({routines.length})
            </button>
            <button
              type="button"
              className={activeTab === 'alerts' ? 'active' : ''}
              onClick={() => setActiveTab('alerts')}
            >
              <Bell size={13} />
              Alertas ({alerts.length})
            </button>
          </div>
          {activeTab === 'routines' && (
            <button
              type="button"
              className="ws-button primary ws-btn-sm"
              onClick={() => {
                setIsCreating(true)
                setSelectedId(null)
                setDetailTab('editor')
              }}
            >
              <Plus size={14} />
              Nova
            </button>
          )}
        </div>

        {activeTab === 'routines' ? (
          <div className="ws-routines-list">
            {routines.map(item => {
              const isSelected = !isCreating && item.id === selectedId
              return (
                <div
                  key={item.id}
                  className={`ws-routine-card ${isSelected ? 'selected' : ''}`}
                  onClick={() => {
                    setIsCreating(false)
                    setSelectedId(item.id)
                  }}
                >
                  <div className="ws-routine-card-head">
                    <strong>{item.name}</strong>
                    <div className="ws-routine-card-actions" onClick={e => e.stopPropagation()}>
                      <button
                        type="button"
                        className="ws-btn-icon"
                        title={item.running ? 'Rotina em execução' : 'Executar agora'}
                        disabled={item.running || runningRoutineId === item.id}
                        onClick={() => handleRunNow(item.id)}
                      >
                        <Play size={13} color={item.running ? 'var(--ws-accent)' : undefined} />
                      </button>
                      <label className="ws-switch" title={item.enabled ? 'Ativa' : 'Desativada'}>
                        <input
                          type="checkbox"
                          checked={item.enabled}
                          onChange={() => handleToggleEnable(item)}
                        />
                        <span className="ws-slider round" />
                      </label>
                    </div>
                  </div>

                  <div className="ws-routine-badges">
                    {(item.trigger_labels || []).map((lbl, idx) => (
                      <span key={idx} className="ws-badge">
                        {lbl}
                      </span>
                    ))}
                  </div>

                  <div className="ws-routine-meta">
                    <span className="ws-next-run">
                      <Clock size={11} />
                      {item.next_run_label || 'sem horário'}
                    </span>
                    {item.last_status && (
                      <span
                        className="ws-status-dot"
                        style={{ color: statusColor(item.last_status) }}
                        title={`Último: ${item.last_status}`}
                      >
                        ● {item.last_status}
                      </span>
                    )}
                  </div>
                </div>
              )
            })}
            {routines.length === 0 && (
              <p className="ws-empty">Nenhuma rotina cadastrada ainda.</p>
            )}
          </div>
        ) : (
          <div className="ws-routines-alerts">
            {alerts.map(alt => (
              <div key={alt.id} className="ws-alert-item">
                <div className="ws-alert-item-head">
                  <span className="ws-alert-badge">
                    <AlertTriangle size={11} /> Alerta
                  </span>
                  <small>{formatTimestamp(alt.started_at)}</small>
                </div>
                <p className="ws-alert-summary">{alt.summary || 'Alerta sem descrição.'}</p>
              </div>
            ))}
            {alerts.length === 0 && (
              <p className="ws-empty">Nenhum alerta recente.</p>
            )}
          </div>
        )}
      </aside>

      {/* Coluna Direita: Editor e Histórico */}
      <main className="ws-routines-main">
        {selectedRoutine || isCreating ? (
          <div className="ws-routines-content">
            <div className="ws-routines-main-header">
              <div className="ws-routines-main-tabs">
                <button
                  type="button"
                  className={detailTab === 'editor' ? 'active' : ''}
                  onClick={() => setDetailTab('editor')}
                >
                  Editor
                </button>
                {!isCreating && (
                  <button
                    type="button"
                    className={detailTab === 'history' ? 'active' : ''}
                    onClick={() => setDetailTab('history')}
                  >
                    <History size={13} />
                    Histórico
                  </button>
                )}
              </div>

              {!isCreating && selectedRoutine && (
                <div className="ws-routines-header-btns">
                  <button
                    type="button"
                    className="ws-button ws-btn-sm"
                    disabled={selectedRoutine.running || runningRoutineId === selectedRoutine.id}
                    onClick={() => handleRunNow(selectedRoutine.id)}
                  >
                    <Play size={13} />
                    Executar agora
                  </button>
                </div>
              )}
            </div>

            {detailTab === 'editor' ? (
              <div className="ws-routines-editor">
                {/* Cabeçalho do formulário */}
                <div className="ws-field-group">
                  <label className="ws-label">
                    Nome da rotina
                    <input
                      type="text"
                      className="ws-input"
                      value={formName}
                      maxLength={120}
                      onChange={e => setFormName(e.target.value)}
                      placeholder="Ex.: Modo Foco, Bom dia..."
                    />
                  </label>
                  <label className="ws-checkbox-label">
                    <input
                      type="checkbox"
                      checked={formEnabled}
                      onChange={e => setFormEnabled(e.target.checked)}
                    />
                    Rotina ativa
                  </label>
                </div>

                {/* Seção de Gatilhos */}
                <fieldset className="ws-fieldset">
                  <legend>Gatilhos</legend>

                  {/* Horário */}
                  <div className="ws-trigger-section">
                    <div className="ws-trigger-title">
                      <Clock size={14} />
                      <strong>Horário e repetição</strong>
                    </div>
                    <div className="ws-grid-2">
                      <label className="ws-label">
                        Tipo de agendamento
                        <select
                          className="ws-select"
                          value={scheduleType}
                          onChange={e => setScheduleType(e.target.value as any)}
                        >
                          <option value="none">Nenhum horário</option>
                          <option value="daily">Todo dia</option>
                          <option value="weekdays">Dias úteis (Seg a Sex)</option>
                          <option value="weekly">Dias específicos da semana</option>
                          <option value="interval">A cada N minutos</option>
                          <option value="at">Uma vez em data/hora específica</option>
                        </select>
                      </label>

                      {scheduleType === 'at' && (
                        <label className="ws-label">
                          Data e hora
                          <input
                            type="datetime-local"
                            className="ws-input"
                            value={scheduleDate}
                            onChange={e => setScheduleDate(e.target.value)}
                          />
                        </label>
                      )}

                      {['daily', 'weekdays', 'weekly'].includes(scheduleType) && (
                        <label className="ws-label">
                          Horário (24h)
                          <input
                            type="time"
                            className="ws-input"
                            value={scheduleTime}
                            onChange={e => setScheduleTime(e.target.value)}
                          />
                        </label>
                      )}

                      {scheduleType === 'interval' && (
                        <label className="ws-label">
                          Intervalo (minutos, 5 a 1440)
                          <input
                            type="number"
                            className="ws-input"
                            min={5}
                            max={1440}
                            value={scheduleInterval}
                            onChange={e => setScheduleInterval(Number(e.target.value))}
                          />
                        </label>
                      )}
                    </div>

                    {scheduleType === 'weekly' && (
                      <div className="ws-weekdays-picker">
                        {WEEKDAYS.map(day => {
                          const checked = scheduleDays.includes(day.id)
                          return (
                            <button
                              key={day.id}
                              type="button"
                              className={`ws-weekday-btn ${checked ? 'selected' : ''}`}
                              onClick={() => {
                                setScheduleDays(prev =>
                                  checked ? prev.filter(d => d !== day.id) : [...prev, day.id]
                                )
                              }}
                            >
                              {day.label}
                            </button>
                          )
                        })}
                      </div>
                    )}
                  </div>

                  {/* Voz e Barra */}
                  <div className="ws-grid-2 ws-trigger-section">
                    <label className="ws-label">
                      <span className="ws-inline-icon">
                        <Mic size={14} /> Frase de voz (opcional)
                      </span>
                      <input
                        type="text"
                        className="ws-input"
                        value={voicePhrase}
                        onChange={e => setVoicePhrase(e.target.value)}
                        placeholder="Ex.: modo foco"
                      />
                    </label>

                    <label className="ws-label">
                      <span className="ws-inline-icon">
                        <Terminal size={14} /> Comando / de barra (opcional)
                      </span>
                      <div className="ws-input-prefix">
                        <span>/</span>
                        <input
                          type="text"
                          className="ws-input"
                          value={commandSlash}
                          onChange={e => setCommandSlash(e.target.value.toLowerCase().replace(/[^a-z0-9-]/g, ''))}
                          placeholder="foco"
                        />
                      </div>
                    </label>
                  </div>

                  {/* Evento */}
                  <div className="ws-trigger-section">
                    <label className="ws-checkbox-label">
                      <input
                        type="checkbox"
                        checked={eventEnabled}
                        onChange={e => setEventEnabled(e.target.checked)}
                      />
                      <strong>Gatilho por evento no PC</strong>
                    </label>

                    {eventEnabled && (
                      <div className="ws-event-params">
                        <div className="ws-grid-2">
                          <label className="ws-label">
                            Tipo de evento
                            <select
                              className="ws-select"
                              value={eventType}
                              onChange={e => setEventType(e.target.value)}
                            >
                              <option value="resource">Uso de recurso (CPU/RAM/disco)</option>
                              <option value="app_started">Programa abriu</option>
                              <option value="app_closed">Programa fechou</option>
                              <option value="calendar_before">Compromisso da agenda próximo</option>
                              <option value="idle">Fiquei ausente (ocioso)</option>
                              <option value="returned">Voltei ao PC</option>
                            </select>
                          </label>

                          <label className="ws-label">
                            Modo
                            <select
                              className="ws-select"
                              value={eventMode}
                              onChange={e => setEventMode(e.target.value as any)}
                            >
                              <option value="alert">Só avisar (cria alerta)</option>
                              <option value="run">Executar a rotina</option>
                            </select>
                          </label>
                        </div>

                        {eventType === 'resource' && (
                          <div className="ws-grid-3">
                            <label className="ws-label">
                              Métrica
                              <select
                                className="ws-select"
                                value={eventMetric}
                                onChange={e => setEventMetric(e.target.value)}
                              >
                                <option value="cpu">CPU (%)</option>
                                <option value="ram">Memória RAM (%)</option>
                                <option value="disk">Disco C: (%)</option>
                              </select>
                            </label>
                            <label className="ws-label">
                              Limiar (%)
                              <input
                                type="number"
                                className="ws-input"
                                min={50}
                                max={99}
                                value={eventThreshold}
                                onChange={e => setEventThreshold(Number(e.target.value))}
                              />
                            </label>
                            <label className="ws-label">
                              Por quantos segundos
                              <input
                                type="number"
                                className="ws-input"
                                min={0}
                                max={3600}
                                value={eventForSeconds}
                                onChange={e => setEventForSeconds(Number(e.target.value))}
                              />
                            </label>
                          </div>
                        )}

                        {(eventType === 'app_started' || eventType === 'app_closed') && (
                          <label className="ws-label">
                            Nome do aplicativo ou processo
                            <input
                              type="text"
                              className="ws-input"
                              value={eventAppName}
                              onChange={e => setEventAppName(e.target.value)}
                              placeholder="Ex.: Spotify, chrome, notepad..."
                            />
                          </label>
                        )}

                        {eventType === 'calendar_before' && (
                          <label className="ws-label">
                            Minutos antes do início do compromisso
                            <input
                              type="number"
                              className="ws-input"
                              min={1}
                              max={1440}
                              value={eventMinutes}
                              onChange={e => setEventMinutes(Number(e.target.value))}
                            />
                          </label>
                        )}

                        {(eventType === 'idle' || eventType === 'returned') && (
                          <label className="ws-label">
                            Minutos de inatividade
                            <input
                              type="number"
                              className="ws-input"
                              min={1}
                              max={720}
                              value={eventMinutes}
                              onChange={e => setEventMinutes(Number(e.target.value))}
                            />
                          </label>
                        )}

                        <div className="ws-grid-2">
                          <label className="ws-label">
                            Intervalo entre disparos (minutos de espera)
                            <input
                              type="number"
                              className="ws-input"
                              min={1}
                              max={1440}
                              value={eventCooldown}
                              onChange={e => setEventCooldown(Number(e.target.value))}
                            />
                          </label>
                        </div>
                      </div>
                    )}
                  </div>
                </fieldset>

                {/* Configurações Adicionais */}
                <fieldset className="ws-fieldset">
                  <legend>Opções do agendador</legend>
                  <div className="ws-grid-2">
                    <label className="ws-checkbox-label">
                      <input
                        type="checkbox"
                        checked={formQuietEnabled}
                        onChange={e => setFormQuietEnabled(e.target.checked)}
                      />
                      Horário de silêncio (não executa neste intervalo)
                    </label>

                    {formQuietEnabled && (
                      <div className="ws-quiet-row">
                        <label className="ws-label">
                          Início
                          <input
                            type="time"
                            className="ws-input"
                            value={formQuietStart}
                            onChange={e => setFormQuietStart(e.target.value)}
                          />
                        </label>
                        <label className="ws-label">
                          Fim
                          <input
                            type="time"
                            className="ws-input"
                            value={formQuietEnd}
                            onChange={e => setFormQuietEnd(e.target.value)}
                          />
                        </label>
                      </div>
                    )}
                  </div>

                  <label className="ws-label" style={{ marginTop: '8px' }}>
                    Tolerância ao ligar o PC (minutos, padrão 15)
                    <input
                      type="number"
                      className="ws-input"
                      min={0}
                      max={720}
                      value={formCatchUp}
                      onChange={e => setFormCatchUp(Number(e.target.value))}
                    />
                    <small className="ws-muted">
                      Se o PC estava desligado no horário da rotina e for ligado dentro desta tolerância, executa uma vez.
                    </small>
                  </label>
                </fieldset>

                {/* Seção de Etapas */}
                <fieldset className="ws-fieldset">
                  <div className="ws-fieldset-head">
                    <legend>Etapas ({steps.length}/20)</legend>
                    <button
                      type="button"
                      className="ws-button ws-btn-sm"
                      onClick={addStep}
                      disabled={steps.length >= 20}
                    >
                      <Plus size={13} /> Adicionar etapa
                    </button>
                  </div>

                  <div className="ws-steps-list">
                    {steps.map((step, idx) => {
                      const toolMeta = toolsMeta.find(t => t.tool === step.tool)
                      const operations = toolMeta?.operations || []
                      const selectedOpRisk = operations.find(o => o.name === step.operation)?.risk || toolMeta?.risk || 'low'

                      return (
                        <div key={idx} className="ws-step-card">
                          <div className="ws-step-card-header">
                            <span className="ws-step-index">#{idx + 1}</span>
                            <input
                              type="text"
                              className="ws-step-label-input"
                              value={step.label}
                              onChange={e => updateStep(idx, { label: e.target.value })}
                              placeholder="Nome do passo"
                            />
                            <div className="ws-step-actions">
                              <button
                                type="button"
                                className="ws-btn-icon"
                                disabled={idx === 0}
                                onClick={() => moveStep(idx, 'up')}
                                title="Mover para cima"
                              >
                                <ChevronUp size={14} />
                              </button>
                              <button
                                type="button"
                                className="ws-btn-icon"
                                disabled={idx === steps.length - 1}
                                onClick={() => moveStep(idx, 'down')}
                                title="Mover para baixo"
                              >
                                <ChevronDown size={14} />
                              </button>
                              <button
                                type="button"
                                className="ws-btn-icon danger"
                                onClick={() => removeStep(idx)}
                                title="Remover etapa"
                              >
                                <Trash2 size={14} />
                              </button>
                            </div>
                          </div>

                          <div className="ws-grid-2" style={{ marginTop: '8px' }}>
                            <label className="ws-label">
                              Ferramenta
                              <select
                                className="ws-select"
                                value={step.tool}
                                onChange={e => {
                                  const newTool = e.target.value
                                  const meta = toolsMeta.find(t => t.tool === newTool)
                                  const defaultOp = meta?.operations[0]?.name || ''
                                  updateStep(idx, { tool: newTool, operation: defaultOp, params: {} })
                                }}
                              >
                                {toolsMeta.map(tm => (
                                  <option key={tm.tool} value={tm.tool}>
                                    {tm.tool} ({tm.label.slice(0, 40)})
                                  </option>
                                ))}
                              </select>
                            </label>

                            {operations.length > 0 && (
                              <label className="ws-label">
                                Operação
                                <select
                                  className="ws-select"
                                  value={step.operation}
                                  onChange={e => updateStep(idx, { operation: e.target.value })}
                                >
                                  {operations.map(op => (
                                    <option key={op.name} value={op.name}>
                                      {op.name} ({op.risk === 'high' || op.risk === 'critical' ? 'alto risco' : 'baixo'})
                                    </option>
                                  ))}
                                </select>
                              </label>
                            )}
                          </div>

                          {/* Parâmetros da ferramenta */}
                          {toolMeta && Object.keys(toolMeta.params).length > 0 && (
                            <div className="ws-step-params">
                              {Object.entries(toolMeta.params).map(([pName, pSpec]) => {
                                const val = step.params[pName] ?? ''
                                return (
                                  <label key={pName} className="ws-label">
                                    {pName} {pSpec.description && <small className="ws-muted">({pSpec.description.slice(0, 60)})</small>}
                                    {pSpec.enum ? (
                                      <select
                                        className="ws-select"
                                        value={String(val)}
                                        onChange={e => updateStep(idx, { params: { ...step.params, [pName]: e.target.value } })}
                                      >
                                        <option value="">Selecione...</option>
                                        {pSpec.enum.map(opt => (
                                          <option key={opt} value={opt}>
                                            {opt}
                                          </option>
                                        ))}
                                      </select>
                                    ) : (
                                      <input
                                        type="text"
                                        className="ws-input"
                                        value={String(val)}
                                        onChange={e => updateStep(idx, { params: { ...step.params, [pName]: e.target.value } })}
                                      />
                                    )}
                                  </label>
                                )
                              })}
                            </div>
                          )}

                          {/* Espera e Política de falha */}
                          <div className="ws-grid-3" style={{ marginTop: '8px' }}>
                            <label className="ws-label">
                              Esperar antes (s)
                              <input
                                type="number"
                                className="ws-input"
                                min={0}
                                max={3600}
                                value={step.delay_before}
                                onChange={e => updateStep(idx, { delay_before: Number(e.target.value) })}
                              />
                            </label>

                            <label className="ws-label">
                              Se falhar
                              <select
                                className="ws-select"
                                value={step.on_failure}
                                onChange={e => updateStep(idx, { on_failure: e.target.value as any })}
                              >
                                <option value="stop">Parar rotina</option>
                                <option value="continue">Continuar</option>
                                <option value="retry">Tentar de novo</option>
                              </select>
                            </label>

                            {step.on_failure === 'retry' ? (
                              <label className="ws-label">
                                Tentativas (1 a 3)
                                <input
                                  type="number"
                                  className="ws-input"
                                  min={1}
                                  max={3}
                                  value={step.retries || 1}
                                  onChange={e => updateStep(idx, { retries: Number(e.target.value) })}
                                />
                              </label>
                            ) : (
                              <label className="ws-label">
                                Tempo limite (s, opcional)
                                <input
                                  type="number"
                                  className="ws-input"
                                  min={5}
                                  max={600}
                                  value={step.timeout || ''}
                                  onChange={e => updateStep(idx, { timeout: e.target.value ? Number(e.target.value) : null })}
                                  placeholder="Sem limite"
                                />
                              </label>
                            )}
                          </div>

                          {(selectedOpRisk === 'high' || selectedOpRisk === 'critical') && (
                            <p className="ws-step-risk-notice">
                              Etapa de risco {selectedOpRisk}: pedirá aprovação na Central ao executar, salvo Modo liberado.
                            </p>
                          )}
                        </div>
                      )
                    })}
                    {steps.length === 0 && (
                      <p className="ws-empty">Nenhuma etapa configurada. Clique em "Adicionar etapa".</p>
                    )}
                  </div>
                  <p className="ws-notice-text">
                    Etapas de risco alto ou crítico pedem aprovação na Central, salvo regra ou Modo liberado.
                  </p>
                </fieldset>

                {errorMsg && <p className="ws-msg error">{errorMsg}</p>}
                {statusMsg && <p className="ws-msg ok">{statusMsg}</p>}

                {/* Rodapé de Ações */}
                <div className="ws-routines-footer">
                  <button
                    type="button"
                    className="ws-button primary"
                    disabled={saving}
                    onClick={handleSave}
                  >
                    {saving ? 'Salvando...' : 'Salvar rotina'}
                  </button>
                  <button
                    type="button"
                    className="ws-button"
                    onClick={() => {
                      setIsCreating(false)
                      setSelectedId(routines[0]?.id || null)
                    }}
                  >
                    Cancelar
                  </button>

                  {!isCreating && selectedRoutine && (
                    <button
                      type="button"
                      className="ws-button danger"
                      style={{ marginLeft: 'auto' }}
                      onClick={() => setPendingDeleteId(selectedRoutine.id)}
                    >
                      <Trash2 size={14} /> Excluir
                    </button>
                  )}
                </div>
              </div>
            ) : (
              /* Aba Histórico */
              <div className="ws-routines-history">
                <div className="ws-history-list">
                  {history.map(item => (
                    <div key={item.id} className="ws-history-row">
                      <div className="ws-history-row-main">
                        <div className="ws-history-row-header">
                          <span
                            className="ws-status-badge"
                            style={{ backgroundColor: statusColor(item.status) + '22', color: statusColor(item.status), borderColor: statusColor(item.status) }}
                          >
                            {item.status}
                          </span>
                          <span className="ws-history-trigger">Gatilho: {item.trigger_kind}</span>
                          <span className="ws-history-time">{formatTimestamp(item.started_at)}</span>
                        </div>
                        <p className="ws-history-summary">{item.summary || 'Sem resumo registrado.'}</p>
                      </div>
                      {item.run_id && openRun && (
                        <button
                          type="button"
                          className="ws-button ws-btn-sm"
                          onClick={() => openRun(item.run_id!)}
                        >
                          <ExternalLink size={13} />
                          Ver na Central
                        </button>
                      )}
                    </div>
                  ))}
                  {history.length === 0 && (
                    <p className="ws-empty">Nenhuma execução registrada para esta rotina.</p>
                  )}
                </div>
              </div>
            )}
          </div>
        ) : (
          <div className="ws-routines-empty-state">
            <Clock size={36} color="var(--ws-muted)" />
            <h3>Nenhuma rotina selecionada</h3>
            <p className="ws-muted">Selecione uma rotina ao lado ou crie uma nova para automatizar tarefas no PC.</p>
            <button
              type="button"
              className="ws-button primary"
              onClick={() => {
                setIsCreating(true)
                setSelectedId(null)
                setDetailTab('editor')
              }}
            >
              <Plus size={14} /> Nova rotina
            </button>
          </div>
        )}
      </main>

      {/* Diálogo de confirmação de exclusão */}
      {Boolean(pendingDeleteId) && (
        <ConfirmDialog
          title="Excluir rotina?"
          message="Esta ação apagará a rotina e todo o histórico de execuções dela. Deseja continuar?"
          confirmLabel="Sim, excluir"
          cancelLabel="Cancelar"
          danger
          onConfirm={handleDelete}
          onCancel={() => setPendingDeleteId(null)}
        />
      )}
    </div>
  )
}