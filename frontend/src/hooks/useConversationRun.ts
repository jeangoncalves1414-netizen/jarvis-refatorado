import { panelVisible, onPanelVisibility } from '../utils/panelVisibility'
import { useEffect, useRef, useState } from 'react'
import { panelRequest } from '../utils/panelApi'

type Run = { id: string; session_id: string | null; status: string }
type Snapshot = { session: string; runs: Run[]; error: string }

// Query active requests so cancellation also works after reloading the conversation.
export function useConversationRun(sessionId: string, enabled: boolean, loading: boolean) {
  const [snapshot, setSnapshot] = useState<Snapshot>({ session: '', runs: [], error: '' })
  const [feedback, setFeedback] = useState({ session: '', text: '' })
  const [busy, setBusy] = useState('')
  const session = useRef(sessionId)
  session.current = sessionId
  const cancelLock = useRef(false)
  const requested = useRef<{ session: string; id: string } | null>(null)
  const [revision, setRevision] = useState(0)
  useEffect(() => {
    setFeedback({ session: sessionId, text: '' })
  }, [sessionId, loading])

  useEffect(() => {
    if (!enabled || !sessionId) return
    let controller = new AbortController()
    let disposed = false
    let timer: ReturnType<typeof setTimeout>
    let inFlight = false
    let activeRun = loading
    const refresh = async () => {
      clearTimeout(timer)
      if (disposed || inFlight || (!panelVisible() && !activeRun)) return
      inFlight = true
      controller = new AbortController()
      const timeout = setTimeout(() => controller.abort(), 10000)
      try {
        const pages = await Promise.all(['running', 'awaiting_confirmation', 'cancel_requested'].map(status => {
          const query = new URLSearchParams({ session_id: sessionId, status, limit: '2' })
          return panelRequest<{ runs: Run[] }>(`/api/runs?${query}`, { signal: controller.signal })
        }))
        if (pages.some(page => !Array.isArray(page.runs))) throw new Error('Pedidos de execução indisponíveis.')
        const runs = [...new Map(pages.flatMap(page => page.runs)
          .filter(run => run.session_id === sessionId && ['running', 'awaiting_confirmation', 'cancel_requested'].includes(run.status))
          .map(run => [run.id, run])).values()]
        activeRun = loading || runs.length > 0 || !!requested.current
        if (!disposed) setSnapshot({ session: sessionId, runs, error: '' })
        if (!disposed && runs.length === 1 && runs[0].status === 'cancel_requested') {
          requested.current = { session: sessionId, id: runs[0].id }
        }
        const pending = requested.current
        if (pending?.session === sessionId) {
          const detail = await panelRequest<{ run: Run }>(`/api/runs/${encodeURIComponent(pending.id)}`, { signal: controller.signal })
          if (!disposed && detail.run?.id === pending.id && ['cancelled', 'failed', 'succeeded', 'interrupted'].includes(detail.run.status)) {
            requested.current = null
            setFeedback({ session: sessionId, text: detail.run.status === 'cancelled' ? 'Pedido cancelado. Os efeitos das etapas concluídas foram preservados.' : 'O pedido foi encerrado. Confira o resultado em Execuções.' })
          }
        }
      } catch (err) {
        if (!disposed) setSnapshot(previous => ({
          session: sessionId,
          runs: previous.session === sessionId ? previous.runs : [],
          error: err instanceof Error && err.name !== 'AbortError' ? err.message : 'Sem resposta do servidor. Consulte Execuções.',
        }))
      } finally {
        clearTimeout(timeout)
        controller.abort()
        inFlight = false
        if (!disposed && (panelVisible() || activeRun)) timer = setTimeout(refresh, activeRun ? 2000 : 10000)
      }
    }
    const unsubscribe = onPanelVisibility(() => { clearTimeout(timer); void refresh() })
    void refresh()
    return () => { disposed = true; unsubscribe(); clearTimeout(timer); controller.abort() }
  }, [sessionId, enabled, loading, revision])

  const current = snapshot.session === sessionId ? snapshot : null
  const run = current?.runs.length === 1 ? current.runs[0] : null
  const multiple = (current?.runs.length || 0) > 1
  const stop = async () => {
    if (cancelLock.current) return
    const origin = sessionId
    if (!enabled || !run || current?.error) {
      setFeedback({ session: origin, text: !enabled ? 'Conecte ao backend do PC para controlar as execuções.' : multiple ? 'Há vários pedidos nesta conversa. Escolha o pedido em Execuções.' : current?.error || 'Nenhum pedido em andamento foi identificado nesta conversa.' })
      setRevision(value => value + 1)
      return
    }
    if (run.status === 'cancel_requested' || requested.current?.id === run.id) {
      setFeedback({ session: origin, text: 'Cancelamento solicitado. Aguardando o encerramento da etapa em andamento.' })
      return
    }
    cancelLock.current = true
    setBusy(origin)
    try {
      const response = await panelRequest<{ run: Run }>(`/api/runs/${encodeURIComponent(run.id)}/cancel`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}',
        signal: AbortSignal.timeout(10000),
      })
      if (response.run?.id !== run.id || response.run.session_id !== origin || !['cancel_requested', 'cancelled'].includes(response.run.status)) {
        throw new Error('O servidor não confirmou o cancelamento. Consulte Execuções.')
      }
      if (session.current === origin) {
        requested.current = response.run.status === 'cancel_requested' ? { session: origin, id: run.id } : null
        setSnapshot({ session: origin, runs: response.run.status === 'cancelled' ? [] : [response.run], error: '' })
        setFeedback({ session: origin, text: response.run.status === 'cancelled' ? 'Pedido cancelado. Os efeitos das etapas concluídas foram preservados.' : 'Cancelamento solicitado. Aguardando o encerramento da etapa em andamento.' })
      }
    } catch (err) {
      if (session.current === origin) setFeedback({ session: origin, text: err instanceof Error ? err.message : 'Não foi possível parar o pedido.' })
    } finally {
      cancelLock.current = false
      setBusy('')
      setRevision(value => value + 1)
    }
  }
  return {
    stop,
    hasActive: enabled && !!current?.runs.length,
    canStop: enabled && !!run && !current?.error && ['running', 'awaiting_confirmation'].includes(run.status) && requested.current?.id !== run.id && busy !== sessionId,
    message: busy === sessionId && sessionId ? 'Solicitando cancelamento…'
      : run?.status === 'cancel_requested' ? 'Cancelamento solicitado. Aguardando o encerramento da etapa em andamento.'
      : current?.error || (multiple ? 'Há vários pedidos nesta conversa. Escolha o pedido em Execuções.' : feedback.session === sessionId ? feedback.text : ''),
  }
}
