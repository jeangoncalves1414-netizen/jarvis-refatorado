/** True when Evolute runs inside the Jarvis shell (iframe or packaged mobile app). */
export function isJarvisShell(): boolean {
  if (typeof window === 'undefined') return false
  try {
    const params = new URLSearchParams(window.location.search)
    if (params.get('shell') === 'jarvis') return true
    return window.parent !== window
  } catch {
    return false
  }
}
