import {
  AudioLines, Camera, CloudSun, Download, Droplets, Eye, Film, Flame, MessageSquare, Mic, MonitorCog, Search, Sparkles, Volume2, Wallet, X, Zap,
  type LucideIcon,
} from 'lucide-react'
import { navigation } from '../navigation'
import { WINDOW_FINANCE, WINDOW_PC_CONTROLS } from '../windows/registry'
import type { ChatMode } from '../components/ChatComposer'

// Registro único de comandos. A paleta (Ctrl+K) e o menu "/" do compositor são montados a partir
// daqui. Cada comando tem um id estável: gatilhos futuros (frase de voz, padrão de palmas, agenda)
// devem apontar para esse id e chamar `runCommand`, sem lógica própria.

export type CommandGroup = 'Navegação' | 'Ações Rápidas' | 'Life OS' | 'Mídia & Ferramentas' | 'Sistema'

export type BackendOperation = 'add-water' | 'briefing' | 'backup' | 'vision'
export type LocalOperation = 'new-chat' | 'dictation' | 'toggle-sfx' | 'prefill-weather' | 'stop-request' | 'clear-popups'

export type CommandAction =
  | { kind: 'navigate'; screen: string }
  | { kind: 'open-window'; windowId: string }
  // Popup montado pelo backend sem IA (GET /api/popups/<template>). `argParam` recebe o texto após a palavra.
  | { kind: 'popup'; template: string; argParam?: string }
  | { kind: 'set-mode'; mode: ChatMode }
  | { kind: 'backend'; operation: BackendOperation }
  | { kind: 'local'; operation: LocalOperation }

export type CommandDef = {
  id: string
  label: string
  title: string
  description: string
  aliases: string[]
  // Palavra após "/" (sem acentos, minúscula). Sem palavra, o comando aparece só na paleta.
  slash?: string
  // Dica exibida no menu "/" quando o comando aceita texto depois da palavra.
  argHint?: string
  group: CommandGroup
  action: CommandAction
  // true: o comando em si roda sem modelo/provedor de IA. Só false quando o comando chama a IA.
  worksOffline: boolean
  icon: LucideIcon
}

// Funções fornecidas pelo App. Todas as ações do registro terminam em uma delas.
export type CommandHandlers = {
  navigate: (screen: string) => void
  openWindow: (windowId: string) => void
  setMode: (mode: ChatMode) => void
  prefill: (text: string) => void
  newChat: () => void
  stopRequest: () => void
  toggleDictation: () => void
  toggleSfx: () => void
  addWater: (ml: number) => void
  triggerBriefing: () => void
  triggerBackup: () => void
  captureVision: () => void
  openPopup: (template: string, params: Record<string, string>) => void
  clearPopups: () => void
}

export const WINDOW_LIFE_OS = 'life-os'
export const WINDOW_CINEMA = 'cinema'
export const WINDOW_CAMERAS = 'cameras'
export const WINDOW_LIVE_CALL = 'live-call'

const NAV_SLASH: Record<string, { slash: string; aliases: string[] }> = {
  Dashboard: { slash: 'inicio', aliases: ['home', 'dashboard'] },
  Chat: { slash: 'conversas', aliases: ['chat', 'conversa'] },
  Central: { slash: 'execucoes', aliases: ['central', 'acoes', 'runs'] },
  'Automações': { slash: 'automacoes', aliases: ['rotinas', 'lembretes'] },
  'Memórias': { slash: 'conhecimento', aliases: ['memorias', 'memoria'] },
  'Integrações': { slash: 'integracoes', aliases: [] },
  Estudos: { slash: 'estudos', aliases: ['estudo', 'flashcards'] },
  'Evolução': { slash: 'lifeos', aliases: ['evolucao', 'habitos'] },
  'Calendário': { slash: 'calendario', aliases: ['agenda'] },
  'Painel pessoal': { slash: 'painel', aliases: ['tarefas'] },
  'Análises': { slash: 'metricas', aliases: ['analises', 'logs'] },
  Identidade: { slash: 'perfis', aliases: ['identidade'] },
  'Configurações': { slash: 'config', aliases: ['configuracoes', 'ajustes'] },
}

const navigationCommands: CommandDef[] = navigation.map(item => ({
  id: `nav-${item.id}`,
  label: item.label,
  title: `Abrir ${item.label}`,
  description: item.description,
  aliases: NAV_SLASH[item.id]?.aliases ?? [],
  slash: NAV_SLASH[item.id]?.slash,
  group: 'Navegação',
  action: { kind: 'navigate', screen: item.id },
  worksOffline: true,
  icon: item.icon,
}))

export const commands: CommandDef[] = [
  { id: 'action-stop-request', label: 'Parar pedido', title: 'Parar pedido desta conversa', description: 'Solicitar o cancelamento da execução atual no PC', aliases: ['cancelar', 'parar', 'interromper'], slash: 'parar', group: 'Ações Rápidas', action: { kind: 'local', operation: 'stop-request' }, worksOffline: true, icon: Zap },
  ...navigationCommands,

  // Life OS
  { id: 'lifeos-open', label: 'Life OS (janela)', title: 'Abrir Painel de Evolução (Life OS)', description: 'Janela dedicada de hábitos, treinos e rotina', aliases: ['evolucao', 'habitos', 'treino'], group: 'Life OS', action: { kind: 'open-window', windowId: WINDOW_LIFE_OS }, worksOffline: true, icon: Zap },
  { id: 'lifeos-vice', label: 'Blindagem e foco', title: 'Ver Blindagem & Foco (Anti-Vício)', description: 'Acompanhar dias limpos e metas de sobriedade', aliases: ['anti-vicio', 'sobriedade', 'foco'], slash: 'foco', group: 'Life OS', action: { kind: 'open-window', windowId: WINDOW_LIFE_OS }, worksOffline: true, icon: Flame },
  { id: 'window-finance', label: 'Finanças', title: 'Abrir Finanças', description: 'Registrar e consultar gastos e receitas, sem precisar da IA', aliases: ['gastos', 'despesas', 'receitas', 'dinheiro', 'lancamentos'], slash: 'financas', group: 'Life OS', action: { kind: 'open-window', windowId: WINDOW_FINANCE }, worksOffline: true, icon: Wallet },
  { id: 'lifeos-water', label: 'Água', title: 'Registrar +250ml de Água', description: 'Computar copo de água na meta diária', aliases: ['agua', 'copo', 'hidratacao'], slash: 'agua', group: 'Life OS', action: { kind: 'backend', operation: 'add-water' }, worksOffline: true, icon: Droplets },

  // Ações rápidas
  { id: 'action-new-chat', label: 'Nova conversa', title: 'Nova Conversa', description: 'Iniciar um diálogo limpo no chat', aliases: ['novo', 'limpar'], slash: 'nova', group: 'Ações Rápidas', action: { kind: 'local', operation: 'new-chat' }, worksOffline: true, icon: MessageSquare },
  { id: 'action-live-call', label: 'Conversa por voz', title: 'Abrir conversa por voz', description: 'Falar com o agente em uma ligação contínua', aliases: ['ligacao', 'chamada', 'ligar'], slash: 'voz', group: 'Ações Rápidas', action: { kind: 'open-window', windowId: WINDOW_LIVE_CALL }, worksOffline: false, icon: AudioLines },
  { id: 'action-dictation', label: 'Ditado', title: 'Ditado', description: 'Ditar uma mensagem para o chat', aliases: ['ditar', 'microfone', 'gravar'], slash: 'ditado', group: 'Ações Rápidas', action: { kind: 'local', operation: 'dictation' }, worksOffline: false, icon: Mic },
  { id: 'action-briefing', label: 'Briefing matinal', title: 'Disparar Briefing Matinal', description: 'Ouvir o resumo falado do dia pelo agente', aliases: ['resumo', 'bom dia'], slash: 'briefing', group: 'Ações Rápidas', action: { kind: 'backend', operation: 'briefing' }, worksOffline: false, icon: Volume2 },
  { id: 'action-research', label: 'Pesquisa', title: 'Modo Pesquisa', description: 'Busca profunda na web com fontes atuais', aliases: ['pesquisar', 'buscar', 'research'], slash: 'pesquisa', argHint: 'tema', group: 'Ações Rápidas', action: { kind: 'set-mode', mode: 'research' }, worksOffline: true, icon: Search },
  { id: 'action-planning', label: 'Planejar', title: 'Modo Planejamento', description: 'Raciocínio e plano estruturado por etapas', aliases: ['plano', 'planejamento', 'think'], slash: 'planejar', argHint: 'objetivo', group: 'Ações Rápidas', action: { kind: 'set-mode', mode: 'planning' }, worksOffline: true, icon: Sparkles },
  { id: 'action-weather', label: 'Clima', title: 'Perguntar o clima', description: 'Prepara a pergunta no compositor; você envia quando quiser', aliases: ['tempo', 'temperatura', 'previsao'], slash: 'clima', argHint: 'cidade', group: 'Ações Rápidas', action: { kind: 'local', operation: 'prefill-weather' }, worksOffline: true, icon: CloudSun },

  // Sistema
  { id: 'window-pc-controls', label: 'Controles do PC', title: 'Abrir Controles do PC', description: 'Brilho, bloqueio de tela, volume e mídia, sem precisar da IA', aliases: ['brilho', 'bloquear', 'bloqueio', 'volume', 'monitor'], slash: 'controles', group: 'Sistema', action: { kind: 'open-window', windowId: WINDOW_PC_CONTROLS }, worksOffline: true, icon: MonitorCog },
  { id: 'system-backup', label: 'Backup', title: 'Exportar Backup Completo (ZIP)', description: 'Baixar memórias, bancos de hábitos e configurações', aliases: ['exportar', 'zip'], slash: 'backup', group: 'Sistema', action: { kind: 'backend', operation: 'backup' }, worksOffline: true, icon: Download },
  { id: 'system-clear-popups', label: 'Fechar popups', title: 'Fechar todos os popups', description: 'Fecha os popups do agente na tela e os que estão na fila', aliases: ['popups', 'limpar popups', 'fechar avisos'], group: 'Sistema', action: { kind: 'local', operation: 'clear-popups' }, worksOffline: true, icon: X },
  { id: 'system-sfx-toggle', label: 'Sons da interface', title: 'Alternar sons da interface', description: 'Feedback auditivo procedural da interface', aliases: ['sfx', 'mudo', 'silenciar'], slash: 'sons', group: 'Sistema', action: { kind: 'local', operation: 'toggle-sfx' }, worksOffline: true, icon: Volume2 },

  // Mídia e ferramentas
  { id: 'tool-cinema', label: 'Cinema', title: 'Abrir Cinema & Mídia', description: 'Catálogo de filmes e player integrado', aliases: ['filme', 'serie', 'midia'], slash: 'cinema', group: 'Mídia & Ferramentas', action: { kind: 'open-window', windowId: WINDOW_CINEMA }, worksOffline: true, icon: Film },
  { id: 'tool-vision', label: 'Visão', title: 'Analisar Tela Atual (Visão)', description: 'Captura o monitor e analisa via IA', aliases: ['tela', 'screenshot', 'ver'], slash: 'visao', group: 'Mídia & Ferramentas', action: { kind: 'backend', operation: 'vision' }, worksOffline: false, icon: Eye },
  { id: 'tool-cameras', label: 'Câmeras', title: 'Abrir Painel de Câmeras', description: 'Monitoramento de vídeo e streams', aliases: ['camera', 'cameras', 'video'], slash: 'cameras', group: 'Mídia & Ferramentas', action: { kind: 'open-window', windowId: WINDOW_CAMERAS }, worksOffline: true, icon: Camera },
]

// Busca da paleta: título, descrição, grupo, rótulo e apelidos, sem diferenciar acentos.
export function searchCommands(list: CommandDef[], query: string, titleOf: (command: CommandDef) => { title: string; description: string }) {
  const q = normalizeText(query)
  if (!q) return list
  return list.filter(command => {
    const { title, description } = titleOf(command)
    return [title, description, command.group, command.label, ...command.aliases].some(part => normalizeText(part).includes(q))
  })
}

export function normalizeText(text: string) {
  return text.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase().trim()
}

export function getCommand(id: string) {
  return commands.find(command => command.id === id)
}

// ── Contrato de comando (AQ3, base) ────────────────────────────────────────────
// Descrição serializável de um comando, sem ícone nem função. É o formato que o backend, a voz,
// as rotinas e o celular devem usar para apontar para um comando: sempre pelo `id` estável.
// Ainda não há gatilho de voz, rotina ou palma; só o ponto de entrada comum (`runCommandById`).
export const COMMAND_CONTRACT_VERSION = 1

// Quem disparou o comando. Os nomes seguem a origem planejada para os Runs (PB4 do plano 017).
export const COMMAND_ORIGINS = ['comando', 'paleta', 'voz', 'rotina', 'palma', 'janela', 'celular'] as const
export type CommandOrigin = (typeof COMMAND_ORIGINS)[number]

export type CommandContract = {
  version: typeof COMMAND_CONTRACT_VERSION
  id: string
  label: string
  slash: string | null
  aliases: string[]
  group: CommandGroup
  action: CommandAction
  worksOffline: boolean
}

export function toCommandContract(command: CommandDef): CommandContract {
  return {
    version: COMMAND_CONTRACT_VERSION,
    id: command.id,
    label: command.label,
    slash: command.slash ?? null,
    aliases: [...command.aliases],
    group: command.group,
    action: command.action,
    worksOffline: command.worksOffline,
  }
}

export function getCommandContracts() {
  return commands.map(toCommandContract)
}

export type CommandRunResult =
  | { ok: true; command: CommandDef; origin: CommandOrigin }
  | { ok: false; reason: 'unknown-command'; id: string }

// Ponto de entrada para gatilhos que só conhecem o id do comando (voz, rotina, palma, celular).
// Id desconhecido nunca executa nada.
export function runCommandById(id: string, handlers: CommandHandlers, options: { origin: CommandOrigin; args?: string }): CommandRunResult {
  const command = getCommand(id)
  if (!command) return { ok: false, reason: 'unknown-command', id }
  runCommand(command, handlers, options.args ?? '')
  return { ok: true, command, origin: options.origin }
}

export function getSlashCommands() {
  return commands.filter(command => command.slash)
}

// Filtro do menu "/": prefixo da palavra primeiro, depois rótulo, apelidos e descrição.
export function searchSlashCommands(query: string) {
  const q = normalizeText(query.replace(/^\//, ''))
  const list = getSlashCommands()
  if (!q) return list
  const rank = (command: CommandDef) => {
    const slash = command.slash!
    if (slash === q) return 0
    if (slash.startsWith(q)) return 1
    if (normalizeText(command.label).startsWith(q) || command.aliases.some(alias => normalizeText(alias).startsWith(q))) return 2
    if (slash.includes(q) || normalizeText(command.label).includes(q) || command.aliases.some(alias => normalizeText(alias).includes(q)) || normalizeText(command.description).includes(q)) return 3
    return -1
  }
  return list
    .map((command, index) => ({ command, index, score: rank(command) }))
    .filter(entry => entry.score >= 0)
    .sort((a, b) => a.score - b.score || a.index - b.index)
    .map(entry => entry.command)
}

export type SlashParse =
  | { kind: 'none' }
  | { kind: 'escaped'; text: string }
  | { kind: 'unknown'; word: string }
  | { kind: 'known'; command: CommandDef; args: string }

// Escape: "//texto" é uma mensagem comum que começa com "/". Remove só a primeira barra.
const ESCAPED_SLASH = /^(\s*)\/(\/[\s\S]*)$/

export function isEscapedSlash(text: string) {
  return ESCAPED_SLASH.test(text)
}

export function unescapeSlash(text: string) {
  return text.replace(ESCAPED_SLASH, '$1$2')
}

// Reconhece "/palavra argumentos". Texto que não começa com "/" nunca é comando.
export function parseSlashInput(text: string): SlashParse {
  if (isEscapedSlash(text)) return { kind: 'escaped', text: unescapeSlash(text) }
  const match = /^\s*\/(\S*)\s*([\s\S]*)$/.exec(text)
  if (!match) return { kind: 'none' }
  const word = normalizeText(match[1])
  const list = getSlashCommands()
  const command = list.find(item => item.slash === word) ?? list.find(item => item.aliases.some(alias => normalizeText(alias) === word))
  return command ? { kind: 'known', command, args: match[2].trim() } : { kind: 'unknown', word: match[1] }
}

// Texto exibido que depende do estado atual (gravação, sons ligados).
export function describeCommand(command: CommandDef, state: { recording: boolean; sfxEnabled: boolean }) {
  if (command.id === 'action-dictation') {
    return { title: command.title, description: state.recording ? 'Parar a gravação e transcrever para o chat' : command.description }
  }
  if (command.id === 'system-sfx-toggle') {
    return { title: state.sfxEnabled ? 'Silenciar Sons Táticos (Mudo)' : 'Ativar Sons Táticos (SFX)', description: command.description }
  }
  return { title: command.title, description: command.description }
}

// Executa um comando. `args` só tem efeito em set-mode (vira o texto do compositor, sem enviar)
// e em /clima (completa a pergunta). Nada aqui envia mensagem ao modelo.
export function runCommand(command: CommandDef, handlers: CommandHandlers, args = '') {
  const action = command.action
  switch (action.kind) {
    case 'navigate':
      handlers.navigate(action.screen)
      return
    case 'open-window':
      handlers.openWindow(action.windowId)
      return
    case 'popup':
      handlers.openPopup(action.template, action.argParam && args ? { [action.argParam]: args } : {})
      return
    case 'set-mode':
      handlers.setMode(action.mode)
      if (args) handlers.prefill(args)
      return
    case 'backend':
      if (action.operation === 'add-water') handlers.addWater(250)
      else if (action.operation === 'briefing') handlers.triggerBriefing()
      else if (action.operation === 'backup') handlers.triggerBackup()
      else handlers.captureVision()
      return
    case 'local':
      if (action.operation === 'stop-request') { handlers.stopRequest(); handlers.navigate('Chat') }
      else if (action.operation === 'new-chat') { handlers.newChat(); handlers.navigate('Chat') }
      else if (action.operation === 'dictation') { handlers.toggleDictation(); handlers.navigate('Chat') }
      else if (action.operation === 'toggle-sfx') handlers.toggleSfx()
      else if (action.operation === 'clear-popups') handlers.clearPopups()
      else handlers.prefill(args ? `Qual o clima em ${args}?` : 'Qual o clima em ')
      return
  }
}
