import { FormEvent, useRef, useState } from 'react'
import { X } from 'lucide-react'
import type { BridgeDevice, BridgeStatus, Climate, Proactive } from '../types'
import { StatusBadge } from '../components/StatusBadge'

type AutomationsPageProps = {
  climate: Climate | null
  bridge: BridgeStatus | null
  proactive: Proactive | null
  reminderMessage: string
  reminderTime: string
  onReminderMessageChange: (value: string) => void
  onReminderTimeChange: (value: string) => void
  onAddReminder: (event: FormEvent) => void
  onSetTemperature: (value: number) => void
  onTriggerBriefing: () => void
  onRegisterBridgeDemo: () => void
  onBridgeCommand: (targetId: string, command: 'turn_on' | 'turn_off') => void
  onRemoveDevice: (deviceId: string) => Promise<void>
}

export function AutomationsPage({
  climate,
  bridge,
  proactive,
  reminderMessage,
  reminderTime,
  onReminderMessageChange,
  onReminderTimeChange,
  onAddReminder,
  onSetTemperature,
  onTriggerBriefing,
  onRegisterBridgeDemo,
  onBridgeCommand,
  onRemoveDevice,
}: AutomationsPageProps) {
  const removeDialog = useRef<HTMLDialogElement>(null)
  const [removeTarget, setRemoveTarget] = useState<BridgeDevice | null>(null)
  const [removing, setRemoving] = useState(false)
  const [removeError, setRemoveError] = useState('')
  const askRemoval = (device: BridgeDevice) => { setRemoveTarget(device); setRemoveError(''); removeDialog.current?.showModal() }
  const confirmRemoval = async () => {
    if (!removeTarget) return
    setRemoving(true)
    try {
      await onRemoveDevice(removeTarget.id)
    } catch (error) {
      setRemoveError(error instanceof Error ? error.message : 'Não foi possível remover o dispositivo.')
    } finally {
      setRemoving(false)
      removeDialog.current?.close()
    }
  }
  return (
    <section className="automation-grid">
      <article className="automation-card">
        <p className="eyebrow">CONTROLE LOCAL</p>
        <h2>Clima</h2>
        <p>
          Ajuste de temperatura salvo pelo Jarvis. A integração física com o dispositivo pode ser adicionada
          depois.
        </p>
        <div className="temperature">
          <strong>{climate?.target_c ?? 22}°</strong>
          <div className="temperature-controls">
            <button
              type="button"
              aria-label="Diminuir temperatura"
              onClick={() => onSetTemperature(Math.max(16, (climate?.target_c ?? 22) - 1))}
            >
              −
            </button>
            <input
              aria-label="Temperatura alvo"
              type="range"
              min="16"
              max="30"
              value={climate?.target_c ?? 22}
              onChange={event => onSetTemperature(Number(event.target.value))}
            />
            <button
              type="button"
              aria-label="Aumentar temperatura"
              onClick={() => onSetTemperature(Math.min(30, (climate?.target_c ?? 22) + 1))}
            >
              +
            </button>
          </div>
          <span>{climate?.current_c !== undefined ? `Ambiente: ${climate.current_c}°` : 'Controle pronto'}</span>
        </div>
      </article>
      <article className="automation-card bridge-card">
        <div className="bridge-card-header">
          <div>
            <p className="eyebrow">PONTE LOCAL</p>
            <h2>Dispositivos conectados</h2>
          </div>
          <span className="bridge-protocol">{bridge?.protocol || 'jarvis-bridge-v1'}</span>
        </div>
        <p>
          O PC e o futuro app móvel compartilharão este contrato. O código é usado apenas para parear clientes na mesma rede.
        </p>
        <div className="bridge-pair-code">{bridge?.pairing_code || '—'}</div>
        <div className="bridge-device-list">
          {(bridge?.devices || []).map(device => (
            <div className="bridge-device" key={device.id}>
              <div>
                <strong>{device.name || device.id}</strong>
                <StatusBadge status={device.connected ? 'success' : 'warning'}>
                  {device.connected ? '● conectado' : '○ offline'} · {device.platform || 'cliente'}
                </StatusBadge>
              </div>
              <div className="bridge-device-actions">
                {device.kind === 'light' ? (
                  <>
                    <button type="button" onClick={() => onBridgeCommand(device.id, 'turn_on')}>Ligar</button>
                    <button type="button" className="secondary" onClick={() => onBridgeCommand(device.id, 'turn_off')}>Desligar</button>
                  </>
                ) : null}
                <button type="button" className="secondary" aria-label={`Remover ${device.name || device.id}`} disabled={removing} onClick={() => askRemoval(device)}>Remover</button>
              </div>
            </div>
          ))}
          {!bridge?.devices?.length ? <span className="empty-state">Nenhum cliente conectado.</span> : null}
        </div>
        {removeError && <div className="ws-error" role="alert"><span>{removeError}</span><button type="button" className="ws-icon-button" aria-label="Fechar erro" onClick={() => setRemoveError('')}><X size={16} /></button></div>}
        {bridge?.events?.length ? (
          <div className="bridge-event-list">
            {bridge.events.slice(-5).reverse().map(event => (
              <span key={event.id}>{String(event.type || '').replace('device.', '')} · executado</span>
            ))}
          </div>
        ) : null}
        <button className="outline-button" type="button" onClick={onRegisterBridgeDemo}>Adicionar lâmpada de teste</button>
        <dialog ref={removeDialog} className="ws-confirm-dialog" aria-labelledby="remove-device-title" onCancel={event => { if (removing) event.preventDefault() }}>
          <h2 id="remove-device-title">Remover {removeTarget?.name || removeTarget?.id || 'dispositivo'}?</h2>
          <p>{removeTarget?.id === 'jarvis-desktop'
            ? 'Este é o controle local do PC. Sem ele, Ligar e Desligar deixam de funcionar neste painel. Para voltar, use “Adicionar lâmpada de teste”, que pareia o controle de novo.'
            : 'O dispositivo perde o acesso à ponte. Para voltar, ele precisa ser pareado de novo com o código de pareamento.'}</p>
          <div>
            <button type="button" className="ws-button" disabled={removing} onClick={() => removeDialog.current?.close()}>Manter dispositivo</button>
            <button type="button" className="ws-button danger" disabled={removing} onClick={() => void confirmRemoval()}>{removing ? 'Removendo…' : 'Remover dispositivo'}</button>
          </div>
        </dialog>
      </article>
      <article className="automation-card">
        <p className="eyebrow">ROTINA PROATIVA</p>
        <h2>Briefing diário</h2>
        <p>
          {proactive?.config?.briefing_enabled
            ? `Ativo às ${proactive.config.briefing_time || '08:00'}.`
            : 'Desativado. Configure-o em Configurações.'}
        </p>
        <button className="outline-button" type="button" onClick={onTriggerBriefing}>
          Gerar briefing agora
        </button>
      </article>
      <article className="automation-card">
        <p className="eyebrow">LEMBRETES</p>
        <h2>Próximos</h2>
        <form className="reminder-form" onSubmit={onAddReminder}>
          <input
            aria-label="Mensagem do lembrete"
            value={reminderMessage}
            onChange={event => onReminderMessageChange(event.target.value)}
            placeholder="Ex.: Tomar remédio"
          />
          <input
            aria-label="Quando lembrar"
            value={reminderTime}
            onChange={event => onReminderTimeChange(event.target.value)}
            placeholder="+10m ou 14:30"
          />
          <button type="submit">Adicionar</button>
        </form>
        {proactive?.reminders?.length ? (
          <div className="compact-list">
            {proactive.reminders.slice(0, 5).map(reminder => (
              <p key={reminder.id}>
                <b>{reminder.message}</b>
                <span>
                  {reminder.target_time ? new Date(reminder.target_time).toLocaleString('pt-BR') : 'Pendente'}
                </span>
              </p>
            ))}
          </div>
        ) : (
          <p className="empty-state">Nenhum lembrete pendente.</p>
        )}
      </article>
    </section>
  )
}
