type DesktopWindow = Window & { __jarvisStandby?: boolean }

export const panelVisible = () => !document.hidden && !(window as DesktopWindow).__jarvisStandby

export function onPanelVisibility(callback: () => void) {
  const resumed = () => {
    // WinForms dispara Shown apenas na primeira abertura; foco cobre o retorno pela bandeja.
    ;(window as DesktopWindow).__jarvisStandby = false
    callback()
  }
  document.addEventListener('visibilitychange', callback)
  window.addEventListener('jarvis:visibility', callback)
  window.addEventListener('focus', resumed)
  return () => {
    document.removeEventListener('visibilitychange', callback)
    window.removeEventListener('jarvis:visibility', callback)
    window.removeEventListener('focus', resumed)
  }
}

/** Poll visual data only while visible; resume immediately without overlapping requests. */
export function pollVisible(task: () => unknown | Promise<unknown>, interval: number, immediate = false) {
  let disposed = false, running = false
  let timer: ReturnType<typeof setTimeout> | undefined
  const schedule = () => { if (!disposed && panelVisible()) timer = setTimeout(run, interval) }
  const run = async () => {
    clearTimeout(timer)
    if (disposed || running || !panelVisible()) return
    running = true
    try { await task() } catch { /* The consumer keeps its last usable snapshot. */ }
    finally { running = false; schedule() }
  }
  const changed = () => {
    clearTimeout(timer)
    document.documentElement.toggleAttribute('data-standby', !panelVisible())
    if (panelVisible()) void run()
  }
  const unsubscribe = onPanelVisibility(changed)
  document.documentElement.toggleAttribute('data-standby', !panelVisible())
  if (immediate) void run(); else schedule()
  return () => { disposed = true; clearTimeout(timer); unsubscribe() }
}
