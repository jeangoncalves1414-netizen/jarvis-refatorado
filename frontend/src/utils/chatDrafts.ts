const prefix = 'jarvis-chat-draft:'
export function readDraft(session: string): string {
  try { return localStorage.getItem(prefix + (session || 'new')) || '' } catch { return '' }
}
export function writeDraft(session: string, text: string) {
  try {
    if (text) localStorage.setItem(prefix + (session || 'new'), text)
    else localStorage.removeItem(prefix + (session || 'new'))
  } catch { /* Keep the in-memory draft if storage is unavailable. */ }
}
