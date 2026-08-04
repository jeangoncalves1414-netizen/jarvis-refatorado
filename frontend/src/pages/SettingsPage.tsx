import { Switch } from '../components/Switch'
import type { LlmSettings, Proactive, TtsSettings, Tray, WakeWord } from '../types'

type SettingsPageProps = {
  ttsSettings: TtsSettings | null
  llmSettings: LlmSettings | null
  wakeWord: WakeWord | null
  tray: Tray | null
  proactive: Proactive | null
  briefingTime: string
  briefingTopics: string[]
  briefingInstructions: string
  notice: string
  onSetTtsProvider: (provider: 'gemini' | 'edge') => void
  onSetProvider: (provider: 'gemini' | 'groq') => void
  onSetWakeWordEnabled: (enabled: boolean) => void
  onSetBootEnabled: (enabled: boolean) => void
  speakEnabled: boolean
  onSetSpeakEnabled: (enabled: boolean) => void
  onSaveBriefing: (enabled?: boolean) => void
  onBriefingTimeChange: (value: string) => void
  onToggleBriefingTopic: (topic: string) => void
  onBriefingInstructionsChange: (value: string) => void
}

export function SettingsPage({
  ttsSettings,
  llmSettings,
  wakeWord,
  tray,
  proactive,
  briefingTime,
  briefingTopics,
  briefingInstructions,
  notice,
  onSetTtsProvider,
  onSetProvider,
  onSetWakeWordEnabled,
  onSetBootEnabled,
  speakEnabled,
  onSetSpeakEnabled,
  onSaveBriefing,
  onBriefingTimeChange,
  onToggleBriefingTopic,
  onBriefingInstructionsChange,
}: SettingsPageProps) {
  return (
    <section className="settings-grid">
      <article className="settings-card">
        <p className="eyebrow">VOZ · TTS</p>
        <h2>Síntese de voz</h2>
        <p>Escolha o provedor que lê as respostas em voz alta.</p>
        <div className="provider-list">
          {(['gemini', 'edge'] as const).map(provider => (
            <button
              key={provider}
              type="button"
              className={ttsSettings?.tts_provider === provider ? 'provider-active' : ''}
              onClick={() => onSetTtsProvider(provider)}
            >
              <span>{provider === 'gemini' ? 'Gemini Flash TTS' : 'Edge TTS (Antonio)'}</span>
              <small>{provider === 'gemini' ? 'Voz natural · Charon' : 'Neural PT-BR'}</small>
            </button>
          ))}
        </div>
      </article>
      <article className="settings-card">
        <p className="eyebrow">RESPOSTAS FALADAS</p>
        <h2>Leitura automática</h2>
        <Switch
          label="Ler respostas em voz alta"
          description="Quando ativo, o Jarvis fala as respostas ao tocar no botão de áudio ou em ações automáticas."
          checked={speakEnabled}
          onChange={onSetSpeakEnabled}
          glowColor="blue"
        />
      </article>
      <article className="settings-card">
        <p className="eyebrow">NÚCLEO JARVIS</p>
        <h2>Provedor de IA</h2>
        <p>Escolha qual serviço o backend usa. As chaves permanecem somente na configuração local.</p>
        <div className="provider-list">
          {(['gemini', 'groq'] as const).map(provider => (
            <button
              key={provider}
              type="button"
              className={llmSettings?.llm_provider === provider ? 'provider-active' : ''}
              onClick={() => onSetProvider(provider)}
            >
              <span>{provider === 'gemini' ? 'Gemini' : 'Groq'}</span>
              <small>{llmSettings?.[`${provider}_configured`] ? 'Configurado' : 'Chave não configurada'}</small>
            </button>
          ))}
        </div>
      </article>
      <article className="settings-card">
        <p className="eyebrow">VOZ E INICIALIZAÇÃO</p>
        <h2>Disponibilidade</h2>
        <Switch
          label="Palavra de ativação"
          description={wakeWord?.available ? 'Detector local disponível.' : 'O detector local não está instalado neste computador.'}
          checked={Boolean(wakeWord?.enabled)}
          disabled={!wakeWord?.available}
          onChange={onSetWakeWordEnabled}
          glowColor="purple"
        />
        <Switch
          label="Iniciar com o Windows"
          description="Abre o Jarvis automaticamente no login."
          checked={Boolean(tray?.boot_enabled)}
          onChange={onSetBootEnabled}
          glowColor="blue"
        />
      </article>
      <article className="settings-card briefing-settings">
        <p className="eyebrow">BRIEFING PROATIVO</p>
        <h2>Rotina diária</h2>
        <Switch
          label="Ativar briefing"
          description="O Jarvis prepara o resumo no horário definido."
          checked={Boolean(proactive?.config?.briefing_enabled)}
          onChange={checked => onSaveBriefing(checked)}
          glowColor="green"
        />
        <label className="field-label">
          Horário
          <input type="time" value={briefingTime} onChange={event => onBriefingTimeChange(event.target.value)} />
        </label>
        <div className="topic-list">
          {[
            ['weather', 'Clima'],
            ['tasks', 'Tarefas'],
            ['news', 'Notícias'],
            ['finance', 'Mercado'],
          ].map(([value, label]) => (
            <Switch
              key={value}
              label={label}
              checked={briefingTopics.includes(value)}
              onChange={() => onToggleBriefingTopic(value)}
              glowColor="purple"
            />
          ))}
        </div>
        <label className="field-label">
          Instruções personalizadas
          <input
            value={briefingInstructions}
            onChange={event => onBriefingInstructionsChange(event.target.value)}
            placeholder="Ex.: seja breve e priorize compromissos"
          />
        </label>
        <button className="outline-button" type="button" onClick={() => onSaveBriefing()}>
          Salvar briefing
        </button>
      </article>
      {notice && <p className="settings-notice">{notice}</p>}
    </section>
  )
}
