/**
 * Organização da tela de Configurações (ordem, seções ocultas e favoritas).
 * A chave começa com `lifeos_`, então entra sozinha em `extraData` da sincronização existente.
 */
export const SETTINGS_LAYOUT_KEY = 'lifeos_settings_layout'

export type SettingsLayout = { order: string[]; hidden: string[]; favorites: string[] }

const EMPTY: SettingsLayout = { order: [], hidden: [], favorites: [] }

const strings = (value: unknown): string[] => (Array.isArray(value) ? value.filter((item): item is string => typeof item === 'string') : [])

export function loadSettingsLayout(): SettingsLayout {
  try {
    const raw = JSON.parse(localStorage.getItem(SETTINGS_LAYOUT_KEY) || 'null')
    if (raw && typeof raw === 'object') return { order: strings(raw.order), hidden: strings(raw.hidden), favorites: strings(raw.favorites) }
  } catch { /* ignore */ }
  return { ...EMPTY }
}

export function saveSettingsLayout(layout: SettingsLayout): void {
  try { localStorage.setItem(SETTINGS_LAYOUT_KEY, JSON.stringify(layout)) } catch { /* ignore */ }
}

/** Aplica a ordem salva às seções; ids novos entram no fim, ids desconhecidos são ignorados. Favoritas vêm primeiro. */
export function orderSectionIds(defaultIds: string[], layout: SettingsLayout): string[] {
  const known = new Set(defaultIds)
  const saved = layout.order.filter(id => known.has(id))
  const ordered = [...saved, ...defaultIds.filter(id => !saved.includes(id))]
  const favorites = ordered.filter(id => layout.favorites.includes(id))
  return [...favorites, ...ordered.filter(id => !layout.favorites.includes(id))]
}
