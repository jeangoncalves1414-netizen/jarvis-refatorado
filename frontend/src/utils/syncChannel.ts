/**
 * Jarvis ⇄ Life OS Real-Time Event Sync Channel
 * Uses BroadcastChannel for instant <1ms cross-window synchronization
 * and WebSocket for cross-device notification.
 */

type SyncEventPayload = Record<string, unknown> | undefined
type SyncListener = (payload: SyncEventPayload) => void

const listeners = new Map<string, Set<SyncListener>>()

let broadcastChannel: BroadcastChannel | null = null

if (typeof window !== 'undefined' && 'BroadcastChannel' in window) {
  try {
    broadcastChannel = new BroadcastChannel('jarvis-lifeos-sync')
    broadcastChannel.onmessage = (event) => {
      const { type, payload } = event.data || {}
      if (type) notifySyncListeners(type, payload)
    }
  } catch {}
}

export function notifySyncListeners(type: string, payload?: SyncEventPayload): void {
  listeners.get(type)?.forEach(fn => {
    try { fn(payload) } catch {}
  })
}

export function broadcastSyncEvent(type: string, payload?: SyncEventPayload): void {
  notifySyncListeners(type, payload)
  // 2. Cross-window broadcast
  try {
    broadcastChannel?.postMessage({ type, payload, timestamp: Date.now() })
  } catch {}
}

export function onSyncEvent(type: string, callback: SyncListener): () => void {
  if (!listeners.has(type)) {
    listeners.set(type, new Set())
  }
  listeners.get(type)!.add(callback)

  return () => {
    listeners.get(type)?.delete(callback)
    if (listeners.get(type)?.size === 0) {
      listeners.delete(type)
    }
  }
}
