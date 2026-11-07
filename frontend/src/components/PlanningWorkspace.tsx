import { useCallback, useEffect, useRef, useState } from 'react'
import type { ChatMessage } from '../types'
import { isMobileStandalone } from '../hooks/useDirectChat'

type Workspace = {
  session_id: string
  title: string
  content: string
  is_open: boolean
  updated_at?: number
}

type PlanningResponse = {
  ok?: boolean
  workspace?: Workspace
  preferences?: { auto_open_for_planning?: boolean }
}

type Props = { sessionId: string; messages: ChatMessage[] }

const workspaceStyles = `
.planning-trigger{border:1px solid rgba(183,255,109,.42);border-radius:8px;padding:7px 10px;color:#d6ff71;background:rgba(183,255,109,.06);font:600 10px 'DM Mono',monospace;letter-spacing:.5px;cursor:pointer}.planning-trigger:hover{background:rgba(183,255,109,.13)}
.planning-overlay{position:fixed;z-index:90;inset:0;background:rgba(4,6,10,.72);display:grid;place-items:center;padding:24px;backdrop-filter:blur(8px)}
.planning-panel{width:min(760px,100%);max-height:min(780px,calc(100vh - 48px));display:grid;grid-template-rows:auto auto 1fr auto;overflow:hidden;border:1px solid rgba(183,255,109,.35);border-radius:18px;color:#eef0f3;background:linear-gradient(145deg,#161a20,#0d1015);box-shadow:0 30px 100px rgba(0,0,0,.7)}
.planning-panel-header{display:flex;justify-content:space-between;gap:14px;padding:20px 22px 14px;border-bottom:1px solid rgba(255,255,255,.08)}.planning-panel-header p{margin:0;color:#b7ff6d;font:10px 'DM Mono',monospace;letter-spacing:1.2px}.planning-panel-header h2{margin:5px 0 0;font-size:21px}.planning-close{width:34px;height:34px;border:1px solid rgba(255,255,255,.16);border-radius:9px;color:#d9dce4;background:transparent;font-size:20px;cursor:pointer}
.planning-title{margin:16px 22px 10px;border:0;border-bottom:1px solid rgba(255,255,255,.15);padding:7px 0;color:#fff;background:transparent;font-size:16px;font-weight:650;outline:none}.planning-title:focus{border-color:#b7ff6d}.planning-editor{min-height:270px;resize:vertical;margin:4px 22px 18px;border:1px solid rgba(255,255,255,.12);border-radius:10px;padding:14px;color:#e8ebef;background:#090c10;font:13px/1.65 'DM Mono',monospace;outline:none}.planning-editor:focus{border-color:rgba(183,255,109,.65)}
.planning-footer{display:flex;flex-wrap:wrap;align-items:center;justify-content:space-between;gap:12px;padding:14px 22px;border-top:1px solid rgba(255,255,255,.08)}.planning-pref{display:flex;align-items:center;gap:8px;color:#aeb4c0;font-size:11px}.planning-save{border:0;border-radius:8px;padding:9px 14px;color:#10150b;background:#b7ff6d;font-weight:700;cursor:pointer}.planning-save:disabled{opacity:.55;cursor:wait}.planning-hint{color:#858d9d;font-size:10px}
@media(max-width:620px){.planning-overlay{padding:0}.planning-panel{width:100%;height:100%;max-height:none;border:0;border-radius:0}.planning-editor{min-height:0}.planning-footer{align-items:flex-start;flex-direction:column}}
`

export function PlanningWorkspace({ sessionId, messages }: Props) {
  const [open, setOpen] = useState(false)
  const [title, setTitle] = useState('Plano em construção')
  const [content, setContent] = useState('')
  const [autoOpen, setAutoOpen] = useState(false)
  const [saving, setSaving] = useState(false)
  const dirtyRef = useRef(false)
  const autoOpenedMessagesRef = useRef<Set<string>>(new Set())

  const apply = useCallback((data: PlanningResponse) => {
    if (data.workspace) {
      setOpen(data.workspace.is_open)
      if (!dirtyRef.current) {
        setTitle(data.workspace.title)
        setContent(data.workspace.content)
      }
    }
    if (data.preferences) setAutoOpen(Boolean(data.preferences.auto_open_for_planning))
  }, [])

  const request = useCallback(async (payload?: Record<string, unknown>) => {
    const response = await fetch('/api/planning', payload
      ? { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ session_id: sessionId, ...payload }) }
      : undefined)
    const data = await response.json() as PlanningResponse & { error?: string }
    if (!response.ok) throw new Error(data.error || 'Não foi possível acessar o plano.')
    apply(data)
    return data
  }, [apply, sessionId])

  useEffect(() => {
    if (isMobileStandalone()) return
    dirtyRef.current = false
    request().catch(() => undefined)
  }, [request])

  useEffect(() => {
    if (isMobileStandalone()) return
    const interval = window.setInterval(() => request().catch(() => undefined), 3500)
    return () => window.clearInterval(interval)
  }, [request])

  useEffect(() => {
    if (!autoOpen) return
    const lastUserMessage = [...messages].reverse().find(message => message.role === 'user')?.content.trim()
    if (!lastUserMessage || autoOpenedMessagesRef.current.has(`${sessionId}:${lastUserMessage}`)) return
    if (!/\b(plano|planejar|planejamento|meta(?:s)?|estrat[eé]gia|objetivo(?:s)?)\b/i.test(lastUserMessage)) return
    const key = `${sessionId}:${lastUserMessage}`
    autoOpenedMessagesRef.current.add(key)
    request({ action: 'open' }).catch(() => autoOpenedMessagesRef.current.delete(key))
  }, [autoOpen, messages, request, sessionId])

  const openWorkspace = async () => {
    dirtyRef.current = false
    await request({ action: 'open' })
  }

  const closeWorkspace = async () => {
    dirtyRef.current = false
    await request({ action: 'close' })
  }

  const save = async () => {
    setSaving(true)
    try {
      await request({ action: 'update', title, content })
      dirtyRef.current = false
    } finally {
      setSaving(false)
    }
  }

  const updateAutoOpen = async (enabled: boolean) => {
    await request({ action: 'set_auto_open', enabled })
  }

  return <>
    <style>{workspaceStyles}</style>
    <button type="button" className="planning-trigger" onClick={() => openWorkspace().catch(() => undefined)} title="Abrir painel de planejamento">PLANO</button>
    {open && <div className="planning-overlay" role="dialog" aria-modal="true" aria-label="Painel de planejamento">
      <section className="planning-panel">
        <header className="planning-panel-header">
          <div><p>WORKSPACE VIVO</p><h2>Plano persistente</h2></div>
          <button type="button" className="planning-close" onClick={() => closeWorkspace().catch(() => undefined)} aria-label="Fechar painel">×</button>
        </header>
        <input className="planning-title" value={title} onChange={event => { dirtyRef.current = true; setTitle(event.target.value) }} aria-label="Título do plano" />
        <textarea className="planning-editor" value={content} onChange={event => { dirtyRef.current = true; setContent(event.target.value) }} onKeyDown={event => { if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 's') { event.preventDefault(); save().catch(() => undefined) } }} aria-label="Conteúdo do plano" />
        <footer className="planning-footer">
          <label className="planning-pref"><input type="checkbox" checked={autoOpen} onChange={event => updateAutoOpen(event.target.checked).catch(() => undefined)} /> Abrir automaticamente quando estivermos planejando</label>
          <div><span className="planning-hint">Ctrl + S para salvar</span> <button type="button" className="planning-save" disabled={saving} onClick={() => save().catch(() => undefined)}>{saving ? 'Salvando…' : 'Salvar plano'}</button></div>
        </footer>
      </section>
    </div>}
  </>
}
