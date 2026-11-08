import { useState, useEffect } from 'react'
import { Switch } from '../components/Switch'
import { Eye, EyeOff, KeyRound, RefreshCw, Save, Download } from 'lucide-react'
import type { AiSettings, LlmSettings, OxyyCatalog, OxyySettings, Proactive, SttSettings, TtsSettings, Tray, WakeWord } from '../types'
import { isMobileStandalone, getMobileProvider, getMobileApiKeys, setMobileProvider, setMobileApiKeys, getMobileOxyyModels, setMobileOxyyModels, DEFAULT_MOBILE_KEYS, DEFAULT_OXXY_MODELS, type DirectChatProvider, countKeys, nativeDirectPost } from '../hooks/useDirectChat'
import { isSfxEnabled, setSfxEnabled, playSuccess } from '../utils/sfx'
import { DEFAULT_AGENT_NAME, DEFAULT_AGENT_STYLE, deriveWakePhrase, getStoredAgentProfile, setStoredAgentProfile, type AgentProfile } from '../utils/jarvisVaultKeys'
import {
  DEFAULT_SUPABASE_KEY,
  DEFAULT_SUPABASE_URL,
  getEvoluteSettings,
  isEvoluteCloudConnected,
  saveEvoluteSettings,
  signInEvoluteCloud,
  signUpEvoluteCloud,
  signOutEvoluteCloud,
  autoSignIn,
  isTokenExpired,
  refreshAccessToken,
} from '../utils/evoluteCloud'
import {
  downloadJarvisVault,
  pushJarvisVault,
  autoSyncOnOpen,
  syncJarvisAfterLogin,
} from '../utils/jarvisCloud'
import { maskKeyList } from '../utils/syncMerge'

type SettingsPageProps = {
  ttsSettings: TtsSettings | null
  sttSettings: SttSettings | null
  oxyySettings: OxyySettings | null
  oxyyCatalog: OxyyCatalog | null
  llmSettings: LlmSettings | null
  aiSettings: AiSettings | null
  wakeWord: WakeWord | null
  tray: Tray | null
  proactive: Proactive | null
  briefingTime: string
  briefingTopics: string[]
  briefingInstructions: string
  notice: string
  apiKeys?: Record<string, string>
  onSaveApiKeys?: (keys: Record<string, string>) => void | Promise<void>
  onSetTtsProvider: (provider: 'fish' | 'gemini' | 'edge' | 'oxyy') => void
  onSetProvider: (provider: 'gemini' | 'groq' | 'oxyy') => void
  onSetSttProvider: (provider: 'groq' | 'oxyy' | 'google') => void
  onSaveOxyy: (models: OxyySettings['models']) => void
  onRefreshOxyy: () => void
  onSetWakeWordEnabled: (enabled: boolean) => void
  onSetBootEnabled: (enabled: boolean) => void
  speakEnabled: boolean
  onSetSpeakEnabled: (enabled: boolean) => void
  onSaveBriefing: (enabled?: boolean) => void
  onBriefingTimeChange: (value: string) => void
  onToggleBriefingTopic: (topic: string) => void
  onBriefingInstructionsChange: (value: string) => void
  onNavigate?: (screen: string) => void
}

const providerLabel: Record<string, string> = {
  fish: 'Fish Audio S2.1 Pro ° Oficial',
  gemini: 'Gemini Flash TTS ° Oficial',
  edge: 'Edge TTS (Antonio) ° Local',
  oxyy: 'Oxyy Audio ° Oxyy',
}

const OFFICIAL_PROVIDERS = [
  { id: 'gemini', label: 'Gemini ° Oficial (Google)', desc: 'Rota direta com a API da Google Gemini' },
  { id: 'groq', label: 'Groq ° Oficial (Groq Inc)', desc: 'Processamento ultrarrápido Llama/Whisper' },
  { id: 'openrouter', label: 'OpenRouter ° Oficial', desc: 'Roteamento direto para 100+ modelos' },
  { id: 'fish', label: 'Fish Audio ° Oficial', desc: 'Vozes neurais customizadas' },
]

export function SettingsPage({
  ttsSettings, sttSettings, oxyySettings, oxyyCatalog, llmSettings, aiSettings, wakeWord, tray, proactive,
  briefingTime, briefingTopics, briefingInstructions, notice, apiKeys = {}, onSaveApiKeys,
  onSetTtsProvider, onSetProvider, onSetSttProvider, onSaveOxyy, onRefreshOxyy,
  onSetWakeWordEnabled, onSetBootEnabled, speakEnabled, onSetSpeakEnabled,
  onSaveBriefing, onBriefingTimeChange, onToggleBriefingTopic, onBriefingInstructionsChange,
  onNavigate,
}: SettingsPageProps) {
  const [keyValues, setKeyValues] = useState<Record<string, string>>({
    oxyy: apiKeys.oxyy || '',
    groq: apiKeys.groq || '',
    gemini: apiKeys.gemini || '',
    openrouter: apiKeys.openrouter || '',
    fish: apiKeys.fish || '',
  })

  // Sincroniza quando apiKeys chegar do servidor (fetch assíncrono)
  useEffect(() => {
    const hasAnyKey = Object.values(apiKeys).some(v => v && v.length > 0)
    if (hasAnyKey) {
      setKeyValues(prev => ({
        oxyy: prev.oxyy || apiKeys.oxyy || '',
        groq: prev.groq || apiKeys.groq || '',
        gemini: prev.gemini || apiKeys.gemini || '',
        openrouter: prev.openrouter || apiKeys.openrouter || '',
        fish: prev.fish || apiKeys.fish || '',
      }))
    }
  }, [apiKeys])

  const [visibleKeys, setVisibleKeys] = useState<Record<string, boolean>>({
    oxyy: false,
    groq: false,
    gemini: false,
    openrouter: false,
    fish: false,
  })

  const toggleKeyVisibility = (key: string) => {
    setVisibleKeys(prev => ({ ...prev, [key]: !prev[key] }))
  }

  const handleKeyChange = (key: string, val: string) => {
    setKeyValues(prev => ({ ...prev, [key]: val }))
  }

  const handleSaveKeys = async () => {
    if (onSaveApiKeys) {
      await onSaveApiKeys(keyValues)
    }
    if (!isMobileStandalone() && isEvoluteCloudConnected()) {
      try {
        await pushJarvisVault()
      } catch {
        /* nuvem opcional */
      }
    }
  }

  const modelFields = [
    ['chat', 'Chat / Raciocínio'],
    ['tts', 'Voz / TTS'],
    ['stt', 'Transcrição / STT'],
    ['image', 'Geração de imagem'],
    ['video', 'Geração de vídeo'],
    ['embedding', 'Embeddings / Memória'],
  ] as const

  const routeCards = ['tts', 'stt', 'image', 'video', 'embedding'] as const
  const routeLabels: Record<string, string> = { tts: 'Voz', stt: 'Transcrição', image: 'Imagem', video: 'Vídeo', embedding: 'Embeddings' }

  const [sfxActive, setSfxActive] = useState(isSfxEnabled)

  return (
    <section className="settings-grid">
      <AgentProfileSettings />

      {/* 2. Leitura Automática Switch Card */}
      <article className="settings-card">
        <p className="eyebrow">RESPOSTAS FALADAS</p>
        <h2>Leitura automática</h2>
        <Switch label="Ler respostas em voz alta" description="Quando ativo, o Jarvis fala respostas e ações automáticas." checked={speakEnabled} onChange={onSetSpeakEnabled} glowColor="blue" />
      </article>

      {/* Sons Táticos Switch Card */}
      <article className="settings-card">
        <p className="eyebrow">FEEDBACK AUDITIVO TÁTICO</p>
        <h2>Sons procedurais (SFX)</h2>
        <Switch
          label="Sons táticos da interface"
          description="Cliques sutis, confirmações de comando e sons futuristas sem arquivos pesados."
          checked={sfxActive}
          onChange={(val) => {
            setSfxEnabled(val)
            setSfxActive(val)
            if (val) playSuccess()
          }}
          glowColor="purple"
        />
      </article>

      {/* Backup & Dados do Sistema Card */}
      <article className="settings-card" style={{ display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
        <div>
          <p className="eyebrow">SEGURANÇA & DADOS</p>
          <h2>Backup do Jarvis & Life OS</h2>
          <p>Exporta em 1 clique um arquivo ZIP com todas as memórias, conversas, hábitos e preferências.</p>
        </div>
        <div style={{ marginTop: 16 }}>
          <a
            href="/api/system/backup"
            download
            className="outline-button"
            onClick={() => playSuccess()}
            style={{ display: 'inline-flex', alignItems: 'center', gap: 8, padding: '10px 16px', textDecoration: 'none', background: 'rgba(251,191,36,0.12)', border: '1px solid rgba(251,191,36,0.35)', color: '#fbbf24', borderRadius: 10, fontWeight: 700 }}
          >
            <Download size={15} /> Exportar Backup Completo (ZIP)
          </a>
        </div>
      </article>

      {/* Ferramentas do Sistema & Módulos */}
      {onNavigate && (
        <article className="settings-card" style={{ display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
          <div>
            <p className="eyebrow">FERRAMENTAS DO SISTEMA</p>
            <h2>Módulos avançados</h2>
            <p>Acesse as ferramentas de infraestrutura, controle de ambiente e telemetria.</p>
          </div>
          <div style={{ display: 'flex', gap: 8, marginTop: 16, flexWrap: 'wrap' }}>
            <button
              type="button"
              className="outline-button"
              onClick={() => onNavigate('Automações')}
              style={{ flex: 1, minWidth: 140, padding: '10px', borderRadius: 10, fontSize: 12, fontWeight: 700, display: 'inline-flex', alignItems: 'center', justifyContent: 'center', gap: 6 }}
            >
              ⚡ Automações & Clima
            </button>
            <button
              type="button"
              className="outline-button"
              onClick={() => onNavigate('Análises')}
              style={{ flex: 1, minWidth: 140, padding: '10px', borderRadius: 10, fontSize: 12, fontWeight: 700, display: 'inline-flex', alignItems: 'center', justifyContent: 'center', gap: 6 }}
            >
              📊 Métricas & Logs
            </button>
          </div>
        </article>
      )}

      {/* Desktop-only Backend Cards — hidden on mobile standalone */}
      {!isMobileStandalone() && (
        <>
          {/* 1. Provedor de Voz TTS */}
          <article className="settings-card">
            <p className="eyebrow">SÍNTESE DE VOZ (TTS)</p>
            <h2>Síntese de voz</h2>
            <p>Escolha o provedor que lê as respostas em voz alta.</p>
            <div className="provider-list">
              {(['fish', 'gemini', 'edge', 'oxyy'] as const).map(provider => (
                <button key={provider} type="button" className={ttsSettings?.tts_provider === provider ? 'provider-active' : ''} onClick={() => onSetTtsProvider(provider)}>
                  <span>{providerLabel[provider]}</span>
                  <small>{provider === 'fish' ? (ttsSettings?.fish_configured ? 'Voz personalizada · configurado' : 'Adicione FISH_API_KEY') : provider === 'gemini' ? 'Voz natural · Charon' : provider === 'edge' ? 'Neural PT-BR' : (ttsSettings?.oxyy_configured ? `Modelo ${ttsSettings.oxyy_model || oxyySettings?.models?.tts || 'TTS'}` : 'Adicione OXYY_API_KEYS')}</small>
                </button>
              ))}
            </div>
          </article>

          {/* 3. API Keys Card (Desktop Backend) */}
          <article className="settings-card settings-keys-card" style={{ gridColumn: '1 / -1' }}>
            <div className="settings-card-heading">
              <div>
                <p className="eyebrow">SEGURANÇA & CREDENCIAIS</p>
                <h2>Chaves de API dos Provedores (Desktop)</h2>
              </div>
              <button className="outline-button" type="button" onClick={handleSaveKeys} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <Save size={14} /> Salvar Chaves
              </button>
            </div>
            <p>Insira ou atualize as chaves de API. Separe múltiplas chaves por vírgula para rotação automática. Use o ícone 👁️ para desocultar os caracteres.</p>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: 16, marginTop: 12 }}>
              {/* Oxyy API Key */}
              <div className="field-label">
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
                  <span style={{ display: 'flex', alignItems: 'center', gap: 6, fontWeight: 600 }}>
                    <KeyRound size={14} style={{ color: '#fbbf24' }} /> Oxyy API Key (Catálogo Principal)
                  </span>
                  {keyValues.oxyy && (
                    <span style={{ fontSize: 10, color: '#4ade80', fontWeight: 600 }}>
                      {keyValues.oxyy.split(',').filter(k => k.trim()).length} chave(s) configurada(s){visibleKeys.oxyy ? ` · ${maskKeyList(keyValues.oxyy)}` : ''}
                    </span>
                  )}
                </div>
                <small style={{ color: 'rgba(255,255,255,0.6)', fontSize: 11, marginBottom: 4 }}>Separe múltiplas chaves por vírgula</small>
                <div style={{ display: 'flex', gap: 8, marginTop: 4 }}>
                  <input
                    type="password"
                    value={keyValues.oxyy}
                    onChange={e => handleKeyChange('oxyy', e.target.value)}
                    placeholder="sk-oxyy-...,sk-oxyy-..."
                    style={{ flex: 1 }}
                  />
                  <button
                    type="button"
                    className="outline-button"
                    onClick={() => toggleKeyVisibility('oxyy')}
                    title={visibleKeys.oxyy ? 'Ocultar finais' : 'Mostrar só os 4 últimos caracteres'}
                    style={{ padding: '6px 10px' }}
                  >
                    {visibleKeys.oxyy ? <EyeOff size={14} /> : <Eye size={14} />}
                  </button>
                </div>
              </div>

              {/* Groq API Key */}
              <div className="field-label">
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
                  <span style={{ display: 'flex', alignItems: 'center', gap: 6, fontWeight: 600 }}>
                    <KeyRound size={14} style={{ color: '#78e68c' }} /> Groq API Key ° Oficial
                  </span>
                  {keyValues.groq && (
                    <span style={{ fontSize: 10, color: '#4ade80', fontWeight: 600 }}>
                      {keyValues.groq.split(',').filter(k => k.trim()).length} chave(s) configurada(s){visibleKeys.groq ? ` · ${maskKeyList(keyValues.groq)}` : ''}
                    </span>
                  )}
                </div>
                <small style={{ color: 'rgba(255,255,255,0.6)', fontSize: 11, marginBottom: 4 }}>Separe múltiplas chaves por vírgula</small>
                <div style={{ display: 'flex', gap: 8, marginTop: 4 }}>
                  <input
                    type="password"
                    value={keyValues.groq}
                    onChange={e => handleKeyChange('groq', e.target.value)}
                    placeholder="gsk_...,gsk_..."
                    style={{ flex: 1 }}
                  />
                  <button
                    type="button"
                    className="outline-button"
                    onClick={() => toggleKeyVisibility('groq')}
                    title={visibleKeys.groq ? 'Ocultar finais' : 'Mostrar só os 4 últimos caracteres'}
                    style={{ padding: '6px 10px' }}
                  >
                    {visibleKeys.groq ? <EyeOff size={14} /> : <Eye size={14} />}
                  </button>
                </div>
              </div>

              {/* Gemini API Key */}
              <div className="field-label">
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
                  <span style={{ display: 'flex', alignItems: 'center', gap: 6, fontWeight: 600 }}>
                    <KeyRound size={14} style={{ color: '#a855f7' }} /> Gemini API Key ° Oficial (Google)
                  </span>
                  {keyValues.gemini && (
                    <span style={{ fontSize: 10, color: '#4ade80', fontWeight: 600 }}>
                      {keyValues.gemini.split(',').filter(k => k.trim()).length} chave(s) configurada(s){visibleKeys.gemini ? ` · ${maskKeyList(keyValues.gemini)}` : ''}
                    </span>
                  )}
                </div>
                <small style={{ color: 'rgba(255,255,255,0.6)', fontSize: 11, marginBottom: 4 }}>Separe múltiplas chaves por vírgula</small>
                <div style={{ display: 'flex', gap: 8, marginTop: 4 }}>
                  <input
                    type="password"
                    value={keyValues.gemini}
                    onChange={e => handleKeyChange('gemini', e.target.value)}
                    placeholder="AIzaSy...,AIzaSy..."
                    style={{ flex: 1 }}
                  />
                  <button
                    type="button"
                    className="outline-button"
                    onClick={() => toggleKeyVisibility('gemini')}
                    title={visibleKeys.gemini ? 'Ocultar finais' : 'Mostrar só os 4 últimos caracteres'}
                    style={{ padding: '6px 10px' }}
                  >
                    {visibleKeys.gemini ? <EyeOff size={14} /> : <Eye size={14} />}
                  </button>
                </div>
              </div>

              {/* OpenRouter API Key */}
              <div className="field-label">
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
                  <span style={{ display: 'flex', alignItems: 'center', gap: 6, fontWeight: 600 }}>
                    <KeyRound size={14} style={{ color: '#ffaa00' }} /> OpenRouter API Key ° Oficial
                  </span>
                  {keyValues.openrouter && (
                    <span style={{ fontSize: 10, color: '#4ade80', fontWeight: 600 }}>
                      {keyValues.openrouter.split(',').filter(k => k.trim()).length} chave(s) configurada(s){visibleKeys.openrouter ? ` · ${maskKeyList(keyValues.openrouter)}` : ''}
                    </span>
                  )}
                </div>
                <small style={{ color: 'rgba(255,255,255,0.6)', fontSize: 11, marginBottom: 4 }}>Separe múltiplas chaves por vírgula</small>
                <div style={{ display: 'flex', gap: 8, marginTop: 4 }}>
                  <input
                    type="password"
                    value={keyValues.openrouter}
                    onChange={e => handleKeyChange('openrouter', e.target.value)}
                    placeholder="sk-or-v1-...,sk-or-v1-..."
                    style={{ flex: 1 }}
                  />
                  <button
                    type="button"
                    className="outline-button"
                    onClick={() => toggleKeyVisibility('openrouter')}
                    title={visibleKeys.openrouter ? 'Ocultar finais' : 'Mostrar só os 4 últimos caracteres'}
                    style={{ padding: '6px 10px' }}
                  >
                    {visibleKeys.openrouter ? <EyeOff size={14} /> : <Eye size={14} />}
                  </button>
                </div>
              </div>

              {/* Fish Audio API Key */}
              <div className="field-label">
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
                  <span style={{ display: 'flex', alignItems: 'center', gap: 6, fontWeight: 600 }}>
                    <KeyRound size={14} style={{ color: '#fbbf24' }} /> Fish Audio API Key ° Oficial
                  </span>
                  {keyValues.fish && (
                    <span style={{ fontSize: 10, color: '#4ade80', fontWeight: 600 }}>
                      {keyValues.fish.split(',').filter(k => k.trim()).length} chave(s) configurada(s){visibleKeys.fish ? ` · ${maskKeyList(keyValues.fish)}` : ''}
                    </span>
                  )}
                </div>
                <small style={{ color: 'rgba(255,255,255,0.6)', fontSize: 11, marginBottom: 4 }}>Separe múltiplas chaves por vírgula</small>
                <div style={{ display: 'flex', gap: 8, marginTop: 4 }}>
                  <input
                    type="password"
                    value={keyValues.fish}
                    onChange={e => handleKeyChange('fish', e.target.value)}
                    placeholder="key-...,key-..."
                    style={{ flex: 1 }}
                  />
                  <button
                    type="button"
                    className="outline-button"
                    onClick={() => toggleKeyVisibility('fish')}
                    title={visibleKeys.fish ? 'Ocultar finais' : 'Mostrar só os 4 últimos caracteres'}
                    style={{ padding: '6px 10px' }}
                  >
                    {visibleKeys.fish ? <EyeOff size={14} /> : <Eye size={14} />}
                  </button>
                </div>
              </div>
            </div>
          </article>

          {/* 4. Rotas por Capacidade (Motor Efetivo Status) */}
          <article className="settings-card settings-routes-card">
            <p className="eyebrow">ROTAS POR CAPACIDADE</p>
            <h2>Motor efetivo</h2>
            <p>Cada capacidade possui uma rota principal e um fallback explícito.</p>
            <div className="route-status-grid">
              {routeCards.map(capability => {
                const route = aiSettings?.routes?.[capability]
                return (
                  <div className="route-status" key={capability}>
                    <div>
                      <strong>{routeLabels[capability]}</strong>
                      <span className="route-badge">
                        {route?.effective ? (route.fallback_used ? 'Fallback ° Oficial' : 'Ativo ° Oxyy/Oficial') : 'Chave ausente'}
                      </span>
                    </div>
                    <small>{route?.effective?.provider || '—'} · {route?.effective?.model || 'nenhum modelo'}</small>
                    <em>{route?.reason || 'Rota ainda não carregada.'}</em>
                  </div>
                )
              })}
            </div>
          </article>

          {/* 5. Catálogo Modular Oxyy */}
          <article className="settings-card oxyy-settings-card">
            <div className="settings-card-heading">
              <div>
                <p className="eyebrow">PROVEDORES & CATÁLOGO MODULAR</p>
                <h2>Seleção de Provedores Principais, Modelos e Fallback</h2>
              </div>
              <button className="outline-button" type="button" onClick={onRefreshOxyy} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <RefreshCw size={14} /> Atualizar Catálogo
              </button>
            </div>
            <p>
              Selecione o provedor e modelo principal e a rota de fallback para cada capacidade.
              Opções via Oxyy são sufixadas com <strong>° Oxyy</strong> e provedores diretos com <strong>° Oficial</strong>.
            </p>

            <div style={{ margin: '16px 0', padding: 14, background: 'rgba(255,255,255,0.03)', borderRadius: 10, border: '1px solid rgba(251,191,36,0.2)' }}>
              <label className="field-label" style={{ fontWeight: 700, fontSize: 13, color: '#fbbf24' }}>
                ⚡ PROVEDOR PADRÃO DE IA (CHAT PRINCIPAL)
                <select
                  value={aiSettings?.routes?.chat?.primary?.provider || llmSettings?.llm_provider || 'oxyy'}
                  onChange={event => onSetProvider(event.target.value as 'gemini' | 'groq' | 'oxyy')}
                  style={{ marginTop: 6 }}
                >
                  <option value="oxyy">Oxyy · 200+ modelos ° Catálogo Principal</option>
                  <option value="gemini">Gemini ° Oficial (Google API Direct)</option>
                  <option value="groq">Groq ° Oficial (Groq Llama 3.3 Direct)</option>
                </select>
              </label>
            </div>

            <details className="settings-collapsible" open>
              <summary>
                Configurações por Capacidade
                <span>{oxyySettings?.key_count || 0} chave(s) Oxyy · {oxyyCatalog?.remote ? 'catálogo remoto ativo' : 'referência local'}</span>
              </summary>
              <div className="oxyy-grid">
                {modelFields.filter(([key]) => key !== 'chat' && key !== 'tts').map(([key, label]) => {
                  const options = oxyyCatalog?.models?.[key] || []
                  const defaultModels: Record<string, string> = {
                    stt: 'whisper-1',
                    image: 'dall-e-3',
                    video: 'veo-3',
                    embedding: 'gemini-embedding-001',
                  }
                  return (
                    <div key={key} style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                      <label className="field-label" style={{ fontWeight: 600 }}>
                        {label} — Modelo ° Oxyy
                        <select
                          value={oxyySettings?.models?.[key] || defaultModels[key] || ''}
                          onChange={event => onSaveOxyy({ ...(oxyySettings?.models || {}), [key]: event.target.value })}
                        >
                          <option value={defaultModels[key] || ''}>{defaultModels[key] || label} ° Oxyy</option>
                          {options.filter(m => m.id !== defaultModels[key]).map(model => (
                            <option value={model.id} key={model.id}>
                              {model.name || model.id} ° Oxyy ({model.provider || 'Oxyy'})
                            </option>
                          ))}
                        </select>
                      </label>
                    </div>
                  )
                })}

                {/* TTS Unificado */}
                {(() => {
                  const oxyyTtsOptions = oxyyCatalog?.models?.['tts'] || []
                  const currentTtsProvider = ttsSettings?.tts_provider || 'fish'
                  const currentOxyyTtsModel = oxyySettings?.models?.['tts'] || 'tts-1-hd'
                  const currentValue = currentTtsProvider === 'oxyy'
                    ? `oxyy:${currentOxyyTtsModel}`
                    : currentTtsProvider

                  const handleTtsChange = (val: string) => {
                    if (val.startsWith('oxyy:')) {
                      const model = val.replace('oxyy:', '')
                      onSetTtsProvider('oxyy')
                      onSaveOxyy({ ...(oxyySettings?.models || {}), tts: model })
                    } else {
                      onSetTtsProvider(val as 'fish' | 'gemini' | 'edge' | 'oxyy')
                    }
                  }

                  return (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                      <label className="field-label" style={{ fontWeight: 600 }}>
                        Voz / TTS — Provedor & Modelo
                        <select value={currentValue} onChange={event => handleTtsChange(event.target.value)}>
                          <optgroup label="° Oficial — Provedores Diretos">
                            <option value="fish">Fish Audio S2.1 Pro ° Oficial {ttsSettings?.fish_configured ? '✓' : '(sem chave)'}</option>
                            <option value="gemini">Gemini Flash TTS ° Oficial (Google)</option>
                            <option value="edge">Edge TTS (Antonio) ° Local (Microsoft)</option>
                          </optgroup>
                          <optgroup label="° Oxyy — Via Catálogo">
                            <option value="oxyy:tts-1-hd">tts-1-hd ° Oxyy</option>
                            <option value="oxyy:tts-1">tts-1 ° Oxyy</option>
                            {oxyyTtsOptions
                              .filter(m => m.id !== 'tts-1-hd' && m.id !== 'tts-1')
                              .map(model => (
                                <option value={`oxyy:${model.id}`} key={model.id}>
                                  {model.name || model.id} ° Oxyy ({model.provider || 'Oxyy'})
                                </option>
                              ))}
                          </optgroup>
                        </select>
                      </label>
                      {currentTtsProvider === 'oxyy' && (
                        <label className="field-label" style={{ marginTop: 4 }}>
                          Voz Oxyy
                          <input
                            value={oxyySettings?.models?.tts_voice || 'alloy'}
                            onChange={event => onSaveOxyy({ ...(oxyySettings?.models || {}), tts_voice: event.target.value })}
                            placeholder="alloy, echo, fable, onyx..."
                          />
                        </label>
                      )}
                    </div>
                  )
                })()}

                {/* Chat Model Oxyy */}
                {(aiSettings?.routes?.chat?.primary?.provider === 'oxyy' || llmSettings?.llm_provider === 'oxyy') && (() => {
                  const chatOptions = oxyyCatalog?.models?.['chat'] || []
                  const defaultChatModel = 'gpt-4o-mini'
                  return (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                      <label className="field-label" style={{ fontWeight: 600 }}>
                        Chat / Raciocínio — Modelo ° Oxyy
                        <select
                          value={oxyySettings?.models?.['chat'] || defaultChatModel}
                          onChange={event => onSaveOxyy({ ...(oxyySettings?.models || {}), chat: event.target.value })}
                        >
                          <option value={defaultChatModel}>gpt-4o-mini ° Oxyy</option>
                          {chatOptions.filter(m => m.id !== defaultChatModel).map(model => (
                            <option value={model.id} key={model.id}>
                              {model.name || model.id} ° Oxyy ({model.provider || 'Oxyy'})
                            </option>
                          ))}
                        </select>
                      </label>
                    </div>
                  )
                })()}
              </div>

              <div className="oxyy-footer-row" style={{ gridColumn: '1 / -1', marginTop: 16 }}>
                <label className="field-label" style={{ flex: 1 }}>
                  STT Fallback Principal
                  <select
                    value={sttSettings?.stt_provider || 'groq'}
                    onChange={event => onSetSttProvider(event.target.value as 'groq' | 'oxyy' | 'google')}
                  >
                    <option value="groq">Groq Whisper ° Oficial</option>
                    <option value="oxyy">Oxyy Whisper ° Oxyy</option>
                    <option value="google">Google Speech ° Oficial (Fallback)</option>
                  </select>
                </label>
                <span className="settings-muted">
                  As chaves ficam salvas no backend com criptografia local e são alternadas de forma transparente em caso de limite ou falha.
                </span>
              </div>
            </details>
          </article>

          {/* 6. Disponibilidade (Wake Word & Boot) */}
          <article className="settings-card">
            <p className="eyebrow">VOZ E INICIALIZAÇÃO</p>
            <h2>Disponibilidade</h2>
            <Switch label="Palavra de ativação" description={!wakeWord?.available ? 'Detector local não instalado.' : wakeWord.active ? `Ativo: ouvindo “${wakeWord.phrase || 'a frase do perfil'}”.` : wakeWord.enabled ? 'Ligado, mas a escuta local não está em execução.' : 'Detector local disponível, desligado.'} checked={Boolean(wakeWord?.enabled)} disabled={!wakeWord?.available} onChange={onSetWakeWordEnabled} glowColor="purple" />
            <Switch label="Iniciar com o Windows" description="Abre o Jarvis automaticamente no login." checked={Boolean(tray?.boot_enabled)} onChange={onSetBootEnabled} glowColor="blue" />
          </article>

          {/* 7. Briefing Proativo */}
          <article className="settings-card briefing-settings">
            <p className="eyebrow">BRIEFING PROATIVO</p>
            <h2>Rotina diária</h2>
            <Switch label="Ativar briefing" description="O Jarvis prepara o resumo no horário definido." checked={Boolean(proactive?.config?.briefing_enabled)} onChange={checked => onSaveBriefing(checked)} glowColor="green" />
            <label className="field-label">Horário<input type="time" value={briefingTime} onChange={event => onBriefingTimeChange(event.target.value)} /></label>
            <div className="topic-list">{[['weather', 'Clima'], ['tasks', 'Tarefas'], ['news', 'Notícias'], ['finance', 'Mercado']].map(([value, label]) => <Switch key={value} label={label} checked={briefingTopics.includes(value)} onChange={() => onToggleBriefingTopic(value)} glowColor="purple" />)}</div>
            <label className="field-label">Instruções personalizadas<input value={briefingInstructions} onChange={event => onBriefingInstructionsChange(event.target.value)} placeholder="Ex.: seja breve e priorize compromissos" /></label>
            <button className="outline-button" type="button" onClick={() => onSaveBriefing()}>Salvar briefing</button>
          </article>
        </>
      )}

      <EvoluteSyncSettings />

      {/* Mobile API & Model Configuration Manager */}
      {isMobileStandalone() && <MobileApiConfig />}

      {notice && <p className="settings-notice">{notice}</p>}
    </section>
  )
}

const textareaStyle = { minHeight: 96, resize: 'vertical', border: '1px solid #3a3a45', borderRadius: 11, padding: 12, color: 'inherit', background: '#111117', font: 'inherit', lineHeight: 1.5 } as const

/** Perfil do agente: muda só nome, tom e frase de ativação, nunca permissões ou ferramentas. */
function AgentProfileSettings() {
  const standalone = isMobileStandalone()
  const [name, setName] = useState('')
  const [style, setStyle] = useState('')
  const [wakePhrase, setWakePhrase] = useState('')
  const [status, setStatus] = useState<'loading' | 'idle' | 'saving' | 'saved' | 'error'>('loading')
  const [message, setMessage] = useState('')

  const apply = (profile: AgentProfile) => {
    setName(profile.name)
    setStyle(profile.style)
    setWakePhrase(profile.wake_phrase_custom ? profile.wake_phrase : '')
  }

  useEffect(() => {
    if (standalone) {
      apply(getStoredAgentProfile())
      setStatus('idle')
      return
    }
    let cancelled = false
    fetch('/api/settings/agent-profile')
      .then(async response => {
        const data = await response.json().catch(() => ({}))
        if (!response.ok || !data.ok || !data.profile) throw new Error(data.error || '')
        if (cancelled) return
        apply(data.profile)
        setStoredAgentProfile(data.profile)
        setStatus('idle')
      })
      .catch(error => {
        if (cancelled) return
        apply(getStoredAgentProfile())
        setStatus('error')
        setMessage(error instanceof Error && error.message ? error.message : 'Não foi possível carregar o perfil do agente. Verifique se o backend está ligado.')
      })
    return () => { cancelled = true }
  }, [standalone])

  const edit = (setter: (value: string) => void) => (value: string) => {
    setter(value)
    if (status === 'saved' || status === 'error') {
      setStatus('idle')
      setMessage('')
    }
  }

  const save = async () => {
    const cleanName = name.trim()
    if (!cleanName) {
      setStatus('error')
      setMessage('Informe um nome para o agente.')
      return
    }
    setStatus('saving')
    setMessage('')
    if (standalone) {
      setStoredAgentProfile({ name: cleanName, style: style.trim() || DEFAULT_AGENT_STYLE, wake_phrase: deriveWakePhrase(cleanName), wake_phrase_custom: false })
      apply(getStoredAgentProfile())
      setStatus('saved')
      setMessage('Perfil salvo neste aparelho.')
      return
    }
    try {
      const response = await fetch('/api/settings/agent-profile', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: cleanName, style, wake_phrase: wakePhrase }),
      })
      const data = await response.json().catch(() => ({}))
      if (!response.ok || !data.ok || !data.profile) throw new Error(data.error || '')
      apply(data.profile)
      setStoredAgentProfile(data.profile)
      setStatus('saved')
      setMessage(data.wake_phrase_check?.checked === false ? `Perfil salvo. ${data.wake_phrase_check.message}` : 'Perfil salvo.')
    } catch (error) {
      setStatus('error')
      setMessage(error instanceof Error && error.message && error.message !== 'Failed to fetch' ? error.message : 'Não foi possível salvar o perfil do agente. Verifique se o backend está ligado.')
    }
  }

  const busy = status === 'loading' || status === 'saving'
  const derived = deriveWakePhrase(name.trim() || DEFAULT_AGENT_NAME)

  return (
    <article className="settings-card agent-profile-card" style={{ gridColumn: '1 / -1' }}>
      <p className="eyebrow">IDENTIDADE</p>
      <h2>Perfil do agente</h2>
      <p>Muda só o nome, o tom e a frase de ativação. Permissões, ferramentas e aprovações continuam iguais.</p>
      <label className="field-label">Nome
        <input value={name} maxLength={40} disabled={busy} onChange={event => edit(setName)(event.target.value)} placeholder={DEFAULT_AGENT_NAME} />
      </label>
      <label className="field-label">Personalidade e estilo
        <textarea value={style} maxLength={2000} disabled={busy} onChange={event => edit(setStyle)(event.target.value)} placeholder={DEFAULT_AGENT_STYLE} style={textareaStyle} />
      </label>
      {!standalone && (
        <label className="field-label">Frase de ativação
          <input value={wakePhrase} maxLength={60} disabled={busy} onChange={event => edit(setWakePhrase)(event.target.value)} placeholder={derived} />
          <span className="settings-muted">Em branco, usa “{derived}”. Só letras e espaços, até 4 palavras. Cada palavra precisa existir no vocabulário do detector local.</span>
        </label>
      )}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginTop: 16, flexWrap: 'wrap' }}>
        <button className="outline-button" type="button" disabled={busy} onClick={save}>
          <Save size={14} /> {status === 'saving' ? 'Salvando…' : 'Salvar perfil'}
        </button>
        {status === 'loading' && <span className="settings-muted">Carregando perfil…</span>}
      </div>
      {status === 'error' && message && <p className="ws-error" role="alert" style={{ marginTop: 12 }}>{message}</p>}
      {status === 'saved' && message && <p className="settings-notice" aria-live="polite">{message}</p>}
    </article>
  )
}

function MobileApiConfig() {
  const [provider, setProvider] = useState<DirectChatProvider>(getMobileProvider)
  const [keys, setKeys] = useState<Record<string, string>>(() => getMobileApiKeys())
  const [oxyyModels, setOxyyModels] = useState(() => getMobileOxyyModels())
  const [showKey, setShowKey] = useState<Record<string, boolean>>({})
  const [testResult, setTestResult] = useState<string | null>(null)
  const [testing, setTesting] = useState(false)

  const save = () => {
    setMobileProvider(provider)
    setMobileApiKeys(keys)
    setMobileOxyyModels(oxyyModels)
    setTestResult('✅ Configurações e modelos do Jarvis salvos!')
    setTimeout(() => setTestResult(null), 3000)
  }

  const testConnection = async () => {
    const rawKey = keys[provider] || ''
    const activeKey = rawKey.split(',')[0]?.trim() || ''
    if (!activeKey) { setTestResult(`❌ Insira uma chave de API para ${provider.toUpperCase()} antes de testar.`); return }
    setTesting(true); setTestResult('Testando...')
    try {
      if (provider === 'gemini') {
        const raw = await nativeDirectPost(
          `https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key=${activeKey}`,
          { 'Content-Type': 'application/json' },
          JSON.stringify({ contents: [{ parts: [{ text: 'oi' }] }] })
        )
        const data = JSON.parse(raw)
        if (data.candidates) setTestResult('✅ Conexão OK! Gemini respondeu.')
        else setTestResult(`❌ Erro: ${data.error?.message || 'Sem resposta do Gemini'}`)
      } else {
        const baseUrl = provider === 'oxyy' ? 'https://api.oxyy.ai/v1' : 'https://api.groq.com/openai/v1'
        const model = provider === 'oxyy' ? oxyyModels.chat : 'llama-3.3-70b-versatile'
        const raw = await nativeDirectPost(
          `${baseUrl}/chat/completions`,
          { 'Content-Type': 'application/json', Authorization: `Bearer ${activeKey}` },
          JSON.stringify({ model, messages: [{ role: 'user', content: 'oi' }], max_tokens: 10 })
        )
        const data = JSON.parse(raw)
        if (data.choices) setTestResult(`✅ Conexão OK! ${provider.toUpperCase()} (${model}) respondeu.`)
        else setTestResult(`❌ Erro: ${data.error?.message || 'Resposta inesperada'}`)
      }
    } catch (err) {
      setTestResult(`❌ ${err instanceof Error ? err.message : 'Falha de rede'}`)
    } finally {
      setTesting(false)
    }
  }

  const resetToPcDefaults = () => {
    setProvider('oxyy')
    setKeys(DEFAULT_MOBILE_KEYS)
    setOxyyModels(DEFAULT_OXXY_MODELS)
    setMobileProvider('oxyy')
    setMobileApiKeys(DEFAULT_MOBILE_KEYS)
    setMobileOxyyModels(DEFAULT_OXXY_MODELS)
    setTestResult('✅ Configuração móvel limpa. Informe sua própria chave para conversar.')
    setTimeout(() => setTestResult(null), 3000)
  }

  return (
    <article className="settings-card" style={{ border: '1px solid rgba(0, 218, 248, 0.3)', boxShadow: '0 0 25px rgba(0, 218, 248, 0.1)' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
        <p className="eyebrow" style={{ color: 'var(--jarvis-cyan)' }}>📱 MOBILE · PARIDADE COM DESKTOP</p>
        <button
          type="button"
          onClick={resetToPcDefaults}
          style={{ padding: '4px 8px', borderRadius: 6, background: 'rgba(0, 218, 248, 0.1)', border: '1px solid rgba(0, 218, 248, 0.3)', color: 'var(--jarvis-cyan)', fontSize: 11, fontWeight: 600, cursor: 'pointer' }}
          title="Limpar chaves salvas neste celular"
        >
          🔄 Limpar chaves
        </button>
      </div>
      <h2>Chat do Jarvis (APIs & Modelos)</h2>
      <p style={{ fontSize: 13, color: '#94a3b8', marginBottom: 16 }}>
        Chaves usadas pelo chat e voz do Jarvis neste celular. Evolução e nuvem ficam na seção acima.
      </p>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
        {/* Provedor Principal */}
        <label style={{ fontSize: 12, fontWeight: 700, color: '#94a3b8' }}>PROVEDOR PRINCIPAL (MOBILE)</label>
        <div style={{ display: 'flex', gap: 8 }}>
          {(['oxyy', 'groq', 'gemini'] as DirectChatProvider[]).map(p => (
            <button
              key={p}
              type="button"
              onClick={() => setProvider(p)}
              style={{
                flex: 1, padding: '10px 4px', borderRadius: 10, fontSize: 12, fontWeight: 700,
                border: provider === p ? '1px solid var(--jarvis-cyan)' : '1px solid rgba(255,255,255,0.1)',
                background: provider === p ? 'rgba(0, 218, 248, 0.14)' : 'rgba(255,255,255,0.04)',
                color: provider === p ? 'var(--jarvis-cyan)' : '#94a3b8', cursor: 'pointer',
              }}
            >
              {p === 'oxyy' ? '🔮 Oxxy (PC Default)' : p === 'groq' ? '⚡ Groq' : '🔵 Gemini'}
            </button>
          ))}
        </div>

        {/* Gerenciador de Chaves */}
        <div style={{ padding: 12, borderRadius: 12, background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.08)', display: 'flex', flexDirection: 'column', gap: 10 }}>
          <p style={{ fontSize: 11, fontWeight: 700, color: 'var(--jarvis-cyan)', letterSpacing: 1 }}>🔑 CHAVES DE API (PC & MOBILE)</p>

          {[
            { id: 'oxyy', label: 'Oxyy API Key (Principal)', placeholder: 'sk-oxyy-...' },
            { id: 'groq', label: 'Groq API Keys (separadas por vírgula para rotação)', placeholder: 'gsk_...,gsk_...' },
            { id: 'gemini', label: 'Gemini API Keys (separadas por vírgula para rotação)', placeholder: 'AIzaSy...,AIzaSy...' },
            { id: 'fish', label: 'Fish Audio Keys (separadas por vírgula para rotação)', placeholder: 'key-...,key-...' },
          ].map(item => (
            <div key={item.id} style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <label style={{ fontSize: 11, color: '#cbd5e1', fontWeight: 600 }}>{item.label}</label>
                {keys[item.id] && (
                  <span style={{ fontSize: 10, color: '#4ade80', fontWeight: 600 }}>
                    {countKeys(item.id as DirectChatProvider)} chave(s) configurada(s){showKey[item.id] ? ` · ${maskKeyList(keys[item.id] || '')}` : ''}
                  </span>
                )}
              </div>
              <div style={{ position: 'relative' }}>
                <input
                  type="password"
                  value={keys[item.id] || ''}
                  onChange={e => setKeys(prev => ({ ...prev, [item.id]: e.target.value }))}
                  placeholder={item.placeholder}
                  style={{ width: '100%', padding: '8px 36px 8px 10px', borderRadius: 8, background: 'rgba(0,0,0,0.3)', border: '1px solid rgba(255,255,255,0.1)', color: '#f1f5f9', fontSize: 12, boxSizing: 'border-box', fontFamily: 'monospace' }}
                />
                <button
                  type="button"
                  onClick={() => setShowKey(prev => ({ ...prev, [item.id]: !prev[item.id] }))}
                  style={{ position: 'absolute', right: 8, top: '50%', transform: 'translateY(-50%)', background: 'none', border: 'none', color: '#94a3b8', cursor: 'pointer' }}
                >
                  {showKey[item.id] ? <EyeOff size={14} /> : <Eye size={14} />}
                </button>
              </div>
            </div>
          ))}
        </div>

        {/* Modelo por Capacidade (Oxxy Router) */}
        {provider === 'oxyy' && (
          <div style={{ padding: 12, borderRadius: 12, background: 'rgba(0, 218, 248, 0.03)', border: '1px solid rgba(0, 218, 248, 0.15)', display: 'flex', flexDirection: 'column', gap: 10 }}>
            <p style={{ fontSize: 11, fontWeight: 700, color: 'var(--jarvis-cyan)', letterSpacing: 1 }}>🎯 ROTEAMENTO DE MODELOS (OXXY)</p>
            {[
              { id: 'chat', label: 'Chat / Raciocínio', options: ['codestral-2508', 'gemini-2.5-flash', 'gpt-4o-mini', 'llama-3.3-70b-instruct', 'grok-4'] },
              { id: 'tts', label: 'Síntese de Voz (TTS)', options: ['tts-1-hd', 'eleven_v3', 'gemini-tts'] },
              { id: 'stt', label: 'Transcrição de Áudio (STT)', options: ['whisper-1', 'gpt-4o-mini-transcribe', 'scribe_v1'] },
              { id: 'image', label: 'Geração de Imagem', options: ['dall-e-3', 'flux.1-pro', 'imagen-4'] },
              { id: 'video', label: 'Geração de Vídeo', options: ['veo-3', 'veo-3.1-fast'] },
              { id: 'embedding', label: 'Embeddings / Memória', options: ['gemini-embedding-001'] },
            ].map(cap => (
              <div key={cap.id} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8 }}>
                <span style={{ fontSize: 11, color: '#94a3b8', minWidth: 120 }}>{cap.label}:</span>
                <select
                  value={oxyyModels[cap.id as keyof typeof oxyyModels] || cap.options[0]}
                  onChange={e => setOxyyModels(prev => ({ ...prev, [cap.id]: e.target.value }))}
                  style={{ flex: 1, padding: '6px 8px', borderRadius: 8, background: 'rgba(0,0,0,0.4)', border: '1px solid rgba(255,255,255,0.1)', color: '#f8fafc', fontSize: 12 }}
                >
                  {cap.options.map(m => <option key={m} value={m}>{m}</option>)}
                </select>
              </div>
            ))}
          </div>
        )}

        {testResult && (
          <p style={{ fontSize: 12, padding: '8px 12px', borderRadius: 8, background: testResult.startsWith('✅') ? 'rgba(34,197,94,0.1)' : 'rgba(239,68,68,0.1)', color: testResult.startsWith('✅') ? '#4ade80' : '#f87171' }}>
            {testResult}
          </p>
        )}

        <div style={{ display: 'flex', gap: 8 }}>
          <button
            type="button"
            onClick={testConnection}
            disabled={testing}
            style={{ flex: 1, padding: '10px', borderRadius: 10, background: 'rgba(255,255,255,0.07)', border: '1px solid rgba(255,255,255,0.15)', color: '#e2e8f0', fontSize: 13, fontWeight: 600, cursor: 'pointer' }}
          >
            {testing ? '⏳ Testando...' : '🔌 Testar Conexão'}
          </button>
          <button
            type="button"
            onClick={save}
            style={{ flex: 1, padding: '10px', borderRadius: 10, background: 'rgba(0, 218, 248, 0.15)', border: '1px solid rgba(0, 218, 248, 0.4)', color: 'var(--jarvis-cyan)', fontSize: 13, fontWeight: 700, cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6 }}
          >
            <Save size={14} /> Salvar
          </button>
        </div>
      </div>
    </article>
  )
}

function EvoluteSyncSettings() {
  const mobile = isMobileStandalone()
  const initial = getEvoluteSettings()
  const [email, setEmail] = useState(initial.userEmail || '')
  const [password, setPassword] = useState('')
  const [cloudMessage, setCloudMessage] = useState<string | null>(null)
  const [cloudBusy, setCloudBusy] = useState(false)
  const [cloudConnected, setCloudConnected] = useState(isEvoluteCloudConnected(initial))
  const [showAdvanced, setShowAdvanced] = useState(false)
  const [customUrl, setCustomUrl] = useState(initial.supabaseUrl || '')
  const [customKey, setCustomKey] = useState(initial.supabasePublishableKey || '')

  // Verificar login persistente ao carregar
  useEffect(() => {
    const checkLogin = async () => {
      if (initial.userEmail && initial.supabaseAccessToken) {
        try {
          if (isTokenExpired(initial)) {
            await refreshAccessToken(initial)
          }
          setCloudConnected(true)
          setEmail(initial.userEmail)
        } catch {
          setCloudConnected(false)
        }
      }
    }
    checkLogin()
  }, [initial])

  const handleCloudAuth = async (signup: boolean) => {
    setCloudBusy(true)
    setCloudMessage(null)
    try {
      const currentSettings = getEvoluteSettings()
      const urlToUse = customUrl.trim() || currentSettings.supabaseUrl || DEFAULT_SUPABASE_URL
      const keyToUse = customKey.trim() || currentSettings.supabasePublishableKey || DEFAULT_SUPABASE_KEY
      
      const action = signup ? signUpEvoluteCloud : signInEvoluteCloud
      await action(email, password, {
        ...currentSettings,
        supabaseUrl: urlToUse,
        supabasePublishableKey: keyToUse,
      })
      setPassword('')
      setCloudConnected(true)
      const settings = getEvoluteSettings()
      setEmail(settings.userEmail || email)

      // Sincronização automática imediata ao autenticar
      try {
        const syncMsg = await syncJarvisAfterLogin(isMobileStandalone() ? 'mobile' : 'pc')
        setCloudMessage(`✅ Login realizado com sucesso! ${syncMsg}`)
      } catch (syncErr) {
        setCloudMessage(`✅ Login realizado! (${syncErr instanceof Error ? syncErr.message : 'Pronto para sincronizar'})`)
      }
    } catch (error) {
      const msg = error instanceof Error ? error.message : 'Falha ao conectar à nuvem.'
      if (msg.toLowerCase().includes('failed to fetch')) {
        setCloudMessage('❌ Erro de conexão (Failed to fetch): O domínio do Supabase não foi localizado na rede (DNS). Verifique se o projeto está ativo no painel supabase.com ou atualize a URL/Chave em "Opções de Conexão".')
      } else {
        setCloudMessage(msg)
      }
    } finally {
      setCloudBusy(false)
    }
  }

  const handleCloudSignOut = () => {
    signOutEvoluteCloud()
    setCloudConnected(false)
    setEmail('')
    setCloudMessage('✅ Logout realizado.')
    setTimeout(() => setCloudMessage(null), 3000)
  }

  const handleSaveToCloud = async () => {
    setCloudBusy(true)
    setCloudMessage(null)
    try {
      await pushJarvisVault()
      setCloudMessage('✅ Jarvis salvo na nuvem com sucesso!')
    } catch (error) {
      setCloudMessage(error instanceof Error ? error.message : 'Falha ao salvar na nuvem.')
    } finally {
      setCloudBusy(false)
    }
  }

  const handleSyncFromCloud = async () => {
    setCloudBusy(true)
    setCloudMessage(null)
    try {
      const vault = await downloadJarvisVault()
      const count = Object.values(vault.keys || {}).filter(value => value && typeof value === 'string' && value.trim()).length
      setCloudMessage(`✅ Sincronizado: ${count} provedor(es), ${vault.memories?.length || 0} memórias, hábitos, treino e mais.`)
    } catch (error) {
      setCloudMessage(error instanceof Error ? error.message : 'Falha ao sincronizar com a nuvem.')
    } finally {
      setCloudBusy(false)
    }
  }

  return (
    <article className="settings-card" style={{ border: '1px solid rgba(255,180,0,0.25)' }}>
      <p className="eyebrow" style={{ color: '#ffb400' }}>⚡ EVOLUÇÃO · LIFE OS</p>
      <h2>Sincronização na Nuvem</h2>
      <p style={{ fontSize: 13, color: '#94a3b8', marginBottom: 16 }}>
        Sincronize chaves, modelos, memórias, hábitos, treino e todos os dados entre PC e celular automaticamente.
        Login persistente - você só precisa entrar uma vez.
      </p>

      {cloudConnected ? (
        // USUÁRIO LOGADO
        <div style={{ padding: 14, borderRadius: 12, background: 'rgba(34,197,94,0.1)', border: '1px solid rgba(34,197,94,0.3)', marginBottom: 16 }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
            <div>
              <p style={{ fontSize: 12, fontWeight: 700, color: '#22c55e', marginBottom: 4 }}>✅ CONECTADO</p>
              <p style={{ fontSize: 13, color: '#22c55e' }}>{email}</p>
            </div>
            <button
              className="outline-button"
              type="button"
              onClick={handleCloudSignOut}
              disabled={cloudBusy}
              style={{ padding: '6px 12px', fontSize: 11, borderRadius: 6, borderColor: 'rgba(239,68,68,0.3)', color: '#ef4444' }}
            >
              Sair
            </button>
          </div>
          <p style={{ fontSize: 11, color: '#86efac' }}>
            Sincronização automática ativa. Dados são sincronizados ao abrir o app e quando há mudanças.
          </p>
        </div>
      ) : (
        // USUÁRIO NÃO LOGADO
        <div style={{ padding: 14, borderRadius: 12, background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.08)', marginBottom: 16 }}>
          <p style={{ fontSize: 11, fontWeight: 700, color: '#ffb400', letterSpacing: 1, marginBottom: 8 }}>
            CRIAR CONTA / ENTRAR
          </p>
          <label className="field-label">
            E-mail
            <input type="email" value={email} onChange={e => setEmail(e.target.value)} placeholder="Seu e-mail" />
          </label>
          <label className="field-label">
            Senha
            <input type="password" value={password} onChange={e => setPassword(e.target.value)} placeholder="Senha da nuvem" />
          </label>

          <div style={{ marginTop: 8, marginBottom: 12 }}>
            <button
              type="button"
              onClick={() => setShowAdvanced(prev => !prev)}
              style={{ background: 'transparent', border: 'none', color: '#94a3b8', fontSize: 11, cursor: 'pointer', textDecoration: 'underline' }}
            >
              {showAdvanced ? '▲ Ocultar opções de conexão (Supabase URL/Key)' : '▼ Opções de conexão com a nuvem (Supabase URL/Key)'}
            </button>
            {showAdvanced && (
              <div style={{ marginTop: 8, padding: 10, background: 'rgba(0,0,0,0.3)', borderRadius: 8, border: '1px solid rgba(255,255,255,0.06)' }}>
                <label className="field-label" style={{ fontSize: 11 }}>
                  Supabase Project URL
                  <input
                    type="text"
                    value={customUrl}
                    onChange={e => {
                      setCustomUrl(e.target.value)
                      saveEvoluteSettings({ supabaseUrl: e.target.value.trim() })
                    }}
                    placeholder={DEFAULT_SUPABASE_URL}
                    style={{ fontSize: 11, padding: '6px 8px' }}
                  />
                </label>
                <label className="field-label" style={{ fontSize: 11, marginTop: 6 }}>
                  Supabase Anon/Publishable Key
                  <input
                    type="password"
                    value={customKey}
                    onChange={e => {
                      setCustomKey(e.target.value)
                      saveEvoluteSettings({ supabasePublishableKey: e.target.value.trim() })
                    }}
                    placeholder="Chave publicável do projeto Supabase"
                    style={{ fontSize: 11, padding: '6px 8px' }}
                  />
                </label>
              </div>
            )}
          </div>

          <div style={{ display: 'flex', gap: 8, marginTop: 12, flexWrap: 'wrap' }}>
            <button
              className="primary-button"
              type="button"
              onClick={() => handleCloudAuth(false)}
              disabled={cloudBusy || !email || !password}
              style={{ flex: 1, minWidth: 120 }}
            >
              {cloudBusy ? 'Entrando...' : 'Entrar'}
            </button>
            <button
              className="outline-button"
              type="button"
              onClick={() => handleCloudAuth(true)}
              disabled={cloudBusy || !email || !password}
              style={{ flex: 1, minWidth: 120 }}
            >
              {cloudBusy ? 'Criando...' : 'Criar conta'}
            </button>
          </div>
        </div>
      )}

      {cloudConnected && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            <button
              className="primary-button"
              type="button"
              onClick={handleSaveToCloud}
              disabled={cloudBusy}
              style={{ flex: 1, minWidth: 160, display: 'flex', alignItems: 'center', gap: 6 }}
            >
              <Save size={16} /> Salvar na nuvem
            </button>
            <button
              className="outline-button"
              type="button"
              onClick={handleSyncFromCloud}
              disabled={cloudBusy}
              style={{ flex: 1, minWidth: 160, display: 'flex', alignItems: 'center', gap: 6 }}
            >
              <Download size={16} /> Sincronizar da nuvem
            </button>
          </div>
          <button
            className="outline-button"
            type="button"
            onClick={async () => {
              setCloudBusy(true)
              try {
                await autoSyncOnOpen()
                setCloudMessage('Sincronização automática concluída.')
              } catch (error) {
                setCloudMessage(error instanceof Error ? error.message : 'Falha na sincronização.')
              } finally {
                setCloudBusy(false)
              }
            }}
            disabled={cloudBusy}
            style={{ display: 'flex', alignItems: 'center', gap: 6, justifyContent: 'center' }}
          >
            <RefreshCw size={16} /> Sincronização automática
          </button>
        </div>
      )}

      {cloudMessage && (
        <div style={{
          marginTop: 12,
          padding: 10,
          borderRadius: 8,
          background: cloudMessage.startsWith('✅') ? 'rgba(34,197,94,0.1)' : 'rgba(239,68,68,0.1)',
          border: cloudMessage.startsWith('✅') ? '1px solid rgba(34,197,94,0.3)' : '1px solid rgba(239,68,68,0.3)',
          color: cloudMessage.startsWith('✅') ? '#22c55e' : '#ef4444',
          fontSize: 12,
          textAlign: 'center'
        }}>
          {cloudMessage}
        </div>
      )}
    </article>
  )
}
