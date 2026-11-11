// Envelope dos popups do painel (lote 6). Mesmo formato de app/agent/popups.py (build_popup).
// Chega pelo WebSocket do chat ({type: "ui_popup", popup}), pelo SSE da ligação
// ({status: "popup", popup}), em context.ui_popups da resposta final e em GET /api/popups/<template>.

export type PopupOrigin = 'chat' | 'voice' | 'command'

export type PopupEnvelope<D = unknown> = {
  id: string
  key: string
  template: string
  version: 1
  title: string
  origin: PopupOrigin
  created_at: number
  // 0 = fica até a usuária fechar.
  ttl_ms: number
  pinned: boolean
  data: D
  animate: Record<string, unknown>
}

export type PopupSettings = { enabled: boolean; auto: boolean; ttl_seconds: number; max_visible: number }

export const POPUP_SETTINGS_DEFAULTS: PopupSettings = { enabled: true, auto: true, ttl_seconds: 8, max_visible: 1 }

// Um popup na tela ou na fila. `revision` sobe quando um popup com a mesma chave atualiza este.
export type PopupEntry = {
  popup: PopupEnvelope
  revision: number
  pinned: boolean
  // Popup ativo (ex.: ditado ligado) nunca expira.
  hold: boolean
}
