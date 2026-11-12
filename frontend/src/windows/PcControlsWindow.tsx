import { autoAllows } from '../components/AutoApprovals'
import { useCallback, useEffect, useRef, useState, type ReactNode } from 'react'
import { Lock, Play, RefreshCw, SkipBack, SkipForward, Sun, Volume1, Volume2, VolumeX } from 'lucide-react'
import { ConfirmDialog } from '../components/ConfirmDialog'
import { panelRequest } from '../utils/panelApi'
import type { PcControlsWindowParams, WindowComponentProps } from './registry'

// Janela "Controles do PC". Cada botão chama POST /api/controls/run, que passa pelo Action Kernel e
// aparece na Central de Execuções. O resultado mostrado é o que o servidor devolveu (nunca presumido)
// e nada aqui usa o modelo de IA, então os controles funcionam com o provedor fora do ar.

type Operation = 'get_brightness' | 'set_brightness' | 'lock_screen' | 'volume_up' | 'volume_down' | 'volume_mute' | 'media_play_pause' | 'media_next' | 'media_prev'
type ControlResponse = { ok: boolean; message: string; data?: { brightness?: number }; action?: { id: string; status: string } }
type Status = { kind: 'pending' | 'ok' | 'error'; label: string; message: string }
type BrightnessState = 'loading' | 'ready' | 'unavailable'

const JSON_HEADERS = { 'Content-Type': 'application/json' }
const DEFAULT_LEVEL = 50

function describeError(error: unknown) {
  if (error instanceof TypeError) return 'Sem conexão com o servidor.'
  return error instanceof Error ? error.message : 'Erro desconhecido.'
}

async function runControl(operation: Operation, extra?: { level: number }, signal?: AbortSignal) {
  return panelRequest<ControlResponse>('/api/controls/run', {
    method: 'POST', headers: JSON_HEADERS, signal,
    body: JSON.stringify({ operation, ...extra }),
  })
}

export function PcControlsWindow({ params }: WindowComponentProps<PcControlsWindowParams>) {
  void params
  const [brightnessState, setBrightnessState] = useState<BrightnessState>('loading')
  const [brightnessNote, setBrightnessNote] = useState('')
  const [applied, setApplied] = useState<number | null>(null)
  const [level, setLevel] = useState(DEFAULT_LEVEL)
  const [status, setStatus] = useState<Status | null>(null)
  const [busy, setBusy] = useState(false)
  const [confirmLock, setConfirmLock] = useState(false)
  const mounted = useRef(true)

  useEffect(() => {
    mounted.current = true
    return () => { mounted.current = false }
  }, [])

  const readBrightness = useCallback(async (signal?: AbortSignal) => {
    setBrightnessState('loading')
    setBusy(true)
    setStatus({ kind: 'pending', label: 'Ler brilho', message: 'Lendo o brilho atual…' })
    try {
      const response = await runControl('get_brightness', undefined, signal)
      if (signal?.aborted) return
      const value = response.data?.brightness
      if (typeof value !== 'number') throw new Error('O servidor não informou o brilho atual.')
      setApplied(value)
      setLevel(value)
      setBrightnessState('ready')
      setBrightnessNote('')
      setStatus({ kind: 'ok', label: 'Ler brilho', message: response.message })
    } catch (error) {
      if (signal?.aborted) return
      setBrightnessState('unavailable')
      setBrightnessNote(describeError(error))
      setStatus({ kind: 'error', label: 'Ler brilho', message: describeError(error) })
    } finally {
      if (!signal?.aborted) setBusy(false)
    }
  }, [])

  useEffect(() => {
    const controller = new AbortController()
    void readBrightness(controller.signal)
    return () => controller.abort()
  }, [readBrightness])

  const perform = async (operation: Operation, label: string, extra?: { level: number }) => {
    if (busy) return
    setBusy(true)
    setStatus({ kind: 'pending', label, message: 'Aguardando o servidor…' })
    try {
      const response = await runControl(operation, extra)
      if (!mounted.current) return
      if (operation === 'set_brightness' && typeof response.data?.brightness === 'number') {
        setApplied(response.data.brightness)
        setLevel(response.data.brightness)
      }
      setStatus({ kind: 'ok', label, message: response.message })
    } catch (error) {
      if (!mounted.current) return
      setStatus({ kind: 'error', label, message: describeError(error) })
    } finally {
      if (mounted.current) setBusy(false)
    }
  }

  const brightnessReady = brightnessState === 'ready'
  const canApply = brightnessReady && !busy && level !== applied

  const controlButton = (operation: Operation, label: string, icon: ReactNode) => (
    <button type="button" className="ws-button ws-pc-button" disabled={busy} onClick={() => void perform(operation, label)}>{icon}<span>{label}</span></button>
  )

  return (
    <div className="ws-pc">
      <p className="ws-muted">Funciona sem IA. Cada ação fica registrada na Central de Execuções.</p>

      <section className="ws-pc-section" aria-label="Brilho">
        <div className="ws-pc-title">
          <strong><Sun size={14} /> Brilho</strong>
          <span className="ws-pc-value" aria-live="polite">{brightnessReady ? `${level}%` : '—'}</span>
        </div>
        <input
          type="range" min={0} max={100} step={1} value={level}
          aria-label="Nível de brilho" disabled={!brightnessReady || busy}
          onChange={event => setLevel(Number(event.target.value))}
        />
        {brightnessState === 'unavailable' && <p className="ws-pc-note">Brilho indisponível: {brightnessNote}</p>}
        <div className="ws-pc-row">
          <button type="button" className="ws-button primary" disabled={!canApply} onClick={() => void perform('set_brightness', 'Ajustar brilho', { level })}>Aplicar brilho</button>
          <button type="button" className="ws-button ws-pc-button" disabled={busy} onClick={() => void readBrightness()}><RefreshCw size={14} /><span>Ler de novo</span></button>
        </div>
      </section>

      <section className="ws-pc-section" aria-label="Tela">
        <div className="ws-pc-title"><strong><Lock size={14} /> Tela</strong></div>
        <div className="ws-pc-row">
          <button type="button" className="ws-button ws-pc-button" disabled={busy} onClick={async () => { if (await autoAllows('commands')) await perform('lock_screen', 'Bloquear tela'); else setConfirmLock(true) }}><Lock size={14} /><span>Bloquear tela</span></button>
        </div>
      </section>

      <section className="ws-pc-section" aria-label="Volume">
        <div className="ws-pc-title"><strong><Volume2 size={14} /> Volume</strong></div>
        <div className="ws-pc-row">
          {controlButton('volume_down', 'Diminuir', <Volume1 size={14} />)}
          {controlButton('volume_mute', 'Mudo', <VolumeX size={14} />)}
          {controlButton('volume_up', 'Aumentar', <Volume2 size={14} />)}
        </div>
      </section>

      <section className="ws-pc-section" aria-label="Mídia">
        <div className="ws-pc-title"><strong><Play size={14} /> Mídia</strong></div>
        <div className="ws-pc-row">
          {controlButton('media_prev', 'Anterior', <SkipBack size={14} />)}
          {controlButton('media_play_pause', 'Play/Pausa', <Play size={14} />)}
          {controlButton('media_next', 'Próxima', <SkipForward size={14} />)}
        </div>
      </section>

      <div className={`ws-pc-status ${status?.kind ?? ''}`} role={status?.kind === 'error' ? 'alert' : 'status'} aria-live="polite">
        {status ? <><strong>{status.label}:</strong> {status.kind === 'pending' ? 'pendente. ' : status.kind === 'ok' ? 'concluído. ' : 'falhou. '}{status.message}</> : 'Nenhuma ação executada nesta janela.'}
      </div>

      {confirmLock && (
        <ConfirmDialog
          title="Bloquear a tela?"
          message="A sessão do Windows será bloqueada agora. Você precisará da sua senha ou PIN para voltar."
          confirmLabel="Bloquear"
          onConfirm={() => { setConfirmLock(false); void perform('lock_screen', 'Bloquear tela') }}
          onCancel={() => setConfirmLock(false)}
        />
      )}
    </div>
  )
}
