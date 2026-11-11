import { Activity, BookOpen, CalendarDays, ChartNoAxesCombined, Fingerprint, GraduationCap, House, LayoutDashboard, MessageSquare, Plug, Settings2, Sprout, Workflow } from 'lucide-react'

// Persisted IDs stay compatible with existing installations.
export const navigation = [
  { id: 'Dashboard', label: 'Início', icon: House, group: 'workspace', description: 'Visão geral e próximos passos' },
  { id: 'Chat', label: 'Conversas', icon: MessageSquare, group: 'workspace', description: 'Converse, pesquise e planeje' },
  { id: 'Central', label: 'Execuções', icon: Activity, group: 'workspace', description: 'Ações, aprovações e resultados' },
  { id: 'Automações', label: 'Automações', icon: Workflow, group: 'workspace', description: 'Rotinas, lembretes e dispositivos' },
  { id: 'Memórias', label: 'Conhecimento', icon: BookOpen, group: 'workspace', description: 'Memórias e contexto do agente' },
  { id: 'Integrações', label: 'Integrações', icon: Plug, group: 'workspace', description: 'Disponibilidade das conexões' },
  { id: 'Saúde', label: 'Saúde do Jarvis', icon: Activity, group: 'workspace', description: 'Modelos, microfone, ferramentas e últimos erros' },
  { id: 'Estudos', label: 'Estudos', icon: GraduationCap, group: 'modules', description: 'Sessões, materiais e quadro de estudos' },
  { id: 'Evolução', label: 'Life OS', icon: Sprout, group: 'modules', description: 'Hábitos e evolução pessoal' },
  { id: 'Calendário', label: 'Calendário', icon: CalendarDays, group: 'modules', description: 'Sua agenda' },
  { id: 'Painel pessoal', label: 'Painel pessoal', icon: LayoutDashboard, group: 'modules', description: 'Indicadores pessoais e tarefas' },
  { id: 'Análises', label: 'Métricas', icon: ChartNoAxesCombined, group: 'modules', description: 'Uso, latência e registros' },
  { id: 'Identidade', label: 'Perfis', icon: Fingerprint, group: 'modules', description: 'Identidades locais' },
  { id: 'Configurações', label: 'Configurações', icon: Settings2, group: 'settings', description: 'Modelos, provedores e voz' },
] as const

export type ScreenId = (typeof navigation)[number]['id']

// Lê o pedido de tela que a ferramenta open_screen devolve no contexto da resposta do chat:
// context.tool_results.open_screen.data.ui_screen. Id fora da navegação é ignorado.
export function extractScreenRequest(context: unknown): ScreenId | null {
  const result = (context as { tool_results?: { open_screen?: { ok?: unknown; data?: { ui_screen?: { screen?: unknown } } } } } | null | undefined)?.tool_results?.open_screen
  const screen = result?.ok === true ? result.data?.ui_screen?.screen : undefined
  const item = navigation.find(entry => entry.id === screen)
  return item ? item.id : null
}

export function resolveScreen(stored: string | null) {
  if (stored === 'Analytics') return 'Análises'
  return navigation.some(item => item.id === stored) ? stored! : 'Chat'
}
