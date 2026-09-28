/**
 * Jarvis Desktop & Native Push Notification Manager
 * Integrates with Windows Action Center / OS Notifications
 */

export function isNotificationSupported(): boolean {
  return typeof window !== 'undefined' && 'Notification' in window
}

export function getNotificationPermission(): NotificationPermission {
  if (!isNotificationSupported()) return 'denied'
  return Notification.permission
}

export async function requestNotificationPermission(): Promise<boolean> {
  if (!isNotificationSupported()) return false
  if (Notification.permission === 'granted') return true
  if (Notification.permission !== 'denied') {
    const result = await Notification.requestPermission()
    return result === 'granted'
  }
  return false
}

export type JarvisNotificationOptions = {
  body?: string
  tag?: string
  data?: unknown
  force?: boolean
  onClick?: () => void
}

/**
 * Notify only when document is hidden (user is in another tab/window).
 * Avoids interrupting the user when they are already looking at Jarvis.
 */
export function notifyWhenHidden(title: string, options: JarvisNotificationOptions = {}): Notification | null {
  return showJarvisNotification(title, options)
}

/** Pre-built notification templates for common Jarvis events */
export const JarvisNotifications = {
  briefingReady: () =>
    notifyWhenHidden('☀️ Jarvis · Briefing Matinal', {
      body: 'Seu resumo diário está pronto. Toque para ouvir.',
      tag: 'jarvis-briefing',
    }),

  reminderFired: (text: string) =>
    showJarvisNotification('⏰ Lembrete · Jarvis', {
      body: text,
      tag: 'jarvis-reminder',
      force: true,
    }),

  researchComplete: (topic: string) =>
    notifyWhenHidden('🔬 Pesquisa Concluída', {
      body: `A análise profunda de "${topic}" está pronta no chat.`,
      tag: 'jarvis-research',
    }),

  agentTaskDone: (agentName: string) =>
    notifyWhenHidden(`✅ ${agentName} · Tarefa Concluída`, {
      body: 'Toque para ver o resultado no Jarvis.',
      tag: 'jarvis-agent-done',
    }),

  systemAlert: (message: string) =>
    showJarvisNotification('⚠️ Alerta do Sistema · Jarvis', {
      body: message,
      tag: 'jarvis-system',
      force: true,
    }),
}

export function showJarvisNotification(
  title: string,
  options: JarvisNotificationOptions = {}
): Notification | null {
  if (!isNotificationSupported() || Notification.permission !== 'granted') {
    return null
  }

  // If user is actively focused on the tab and force is not set, skip OS notification
  if (!options.force && typeof document !== 'undefined' && document.visibilityState === 'visible' && document.hasFocus()) {
    return null
  }

  try {
    const notification = new Notification(title, {
      body: options.body,
      icon: '/icon.svg',
      badge: '/icon.svg',
      tag: options.tag || 'jarvis-general',
      data: options.data,
    })

    notification.onclick = () => {
      window.focus()
      notification.close()
      options.onClick?.()
    }

    return notification
  } catch {
    return null
  }
}
