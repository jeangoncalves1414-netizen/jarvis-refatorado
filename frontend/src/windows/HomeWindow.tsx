import { useCallback, useEffect, useState } from 'react'
import {
  Fan,
  Flame,
  House,
  Lightbulb,
  Lock,
  Play,
  Power,
  RefreshCw,
  Settings,
  Shield,
  ToggleLeft,
  ToggleRight,
  Tv,
  Volume2,
} from 'lucide-react'
import type { HomeWindowParams, WindowComponentProps } from './registry'

export type HomeEntity = {
  entity_id: string
  name: string
  domain: string
  state: string
  area: string
}

type StatusNotice = {
  type: 'success' | 'error' | 'pending'
  message: string
}

function domainIcon(domain: string, state: string) {
  const isOn = state === 'on' || state === 'playing' || state === 'locked'
  const style = { color: isOn ? 'var(--ws-accent, #00daf8)' : 'var(--ws-muted, #8fa196)' }

  switch (domain) {
    case 'light':
      return <Lightbulb size={16} style={style} />
    case 'switch':
      return <Power size={16} style={style} />
    case 'fan':
      return <Fan size={16} style={style} />
    case 'media_player':
      return <Volume2 size={16} style={style} />
    case 'scene':
      return <Tv size={16} style={{ color: '#d8c48f' }} />
    case 'script':
      return <Play size={16} style={{ color: '#b4d9c6' }} />
    case 'lock':
      return <Lock size={16} style={style} />
    case 'climate':
      return <Flame size={16} style={style} />
    case 'alarm_control_panel':
      return <Shield size={16} style={{ color: '#eda594' }} />
    default:
      return <House size={16} style={style} />
  }
}

export function HomeWindow({ params }: WindowComponentProps<HomeWindowParams>) {
  void params
  const [loading, setLoading] = useState(true)
  const [configured, setConfigured] = useState(true)
  const [entities, setEntities] = useState<HomeEntity[]>([])
  const [status, setStatus] = useState<StatusNotice | null>(null)
  const [busyId, setBusyId] = useState<string | null>(null)

  const loadEntities = useCallback(async () => {
    setLoading(true)
    try {
      const res = await fetch('/api/home/entities')
      const data = await res.json().catch(() => ({}))
      if (!res.ok) throw new Error(data.error || 'Erro ao carregar aparelhos.')
      setConfigured(Boolean(data.configured))
      setEntities(Array.isArray(data.entities) ? data.entities : [])
    } catch (err) {
      setStatus({
        type: 'error',
        message: err instanceof Error ? err.message : 'Falha ao buscar aparelhos da casa.',
      })
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    loadEntities()
  }, [loadEntities])

  const handleAction = async (operation: string, entityId: string, label: string) => {
    setBusyId(entityId)
    setStatus(null)
    try {
      const res = await fetch('/api/home/action', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ operation, entity: entityId }),
      })
      const data = await res.json().catch(() => ({}))
      if (data.pending) {
        setStatus({
          type: 'pending',
          message: `Ação em '${label}' aguarda aprovação na Central de Execuções.`,
        })
      } else if (data.ok) {
        setStatus({
          type: 'success',
          message: data.message || `Ação concluída em '${label}'.`,
        })
        await loadEntities()
      } else {
        setStatus({
          type: 'error',
          message: data.message || data.error || `Não foi possível acionar '${label}'.`,
        })
      }
    } catch (err) {
      setStatus({
        type: 'error',
        message: err instanceof Error ? err.message : 'Erro ao enviar comando.',
      })
    } finally {
      setBusyId(null)
    }
  }

  const openSettings = () => {
    window.dispatchEvent(new CustomEvent('jarvis:open-settings'))
  }

  if (!loading && !configured) {
    return (
      <div className="ws-home-empty">
        <House size={36} className="ws-home-empty-icon" />
        <h3>Desligado: não configurado</h3>
        <p>
          Conecte sua instância do Home Assistant para visualizar e controlar os aparelhos da sua casa.
        </p>
        <button type="button" className="ws-home-btn-primary" onClick={openSettings}>
          <Settings size={14} />
          Abrir Configurações
        </button>
      </div>
    )
  }

  // Agrupar por área
  const areas = Array.from(new Set(entities.map(e => e.area || 'Sem cômodo')))
  areas.sort((a, b) => (a === 'Sem cômodo' ? 1 : b === 'Sem cômodo' ? -1 : a.localeCompare(b)))

  return (
    <div className="ws-home">
      <div className="ws-home-header">
        <div className="ws-home-title-row">
          <strong>Aparelhos da casa</strong>
          <span className="ws-home-badge">{entities.length} aparelhos</span>
        </div>
        <button
          type="button"
          className="ws-home-refresh-btn"
          onClick={loadEntities}
          disabled={loading}
          title="Atualizar lista de aparelhos"
        >
          <RefreshCw size={13} className={loading ? 'ws-home-spin' : ''} />
          <span>Atualizar</span>
        </button>
      </div>

      {status && (
        <div className={`ws-home-status ${status.type}`}>
          {status.message}
        </div>
      )}

      {loading && entities.length === 0 ? (
        <div className="ws-home-loading">Carregando aparelhos…</div>
      ) : entities.length === 0 ? (
        <div className="ws-home-empty-list">Nenhum aparelho encontrado no Home Assistant.</div>
      ) : (
        <div className="ws-home-areas">
          {areas.map(area => {
            const areaEntities = entities.filter(e => (e.area || 'Sem cômodo') === area)
            return (
              <section key={area} className="ws-home-area-section">
                <h4 className="ws-home-area-title">{area}</h4>
                <div className="ws-home-grid">
                  {areaEntities.map(entity => {
                    const isBusy = busyId === entity.entity_id
                    const isScene = entity.domain === 'scene'
                    const isScript = entity.domain === 'script'
                    const isToggleable = ['light', 'switch', 'fan', 'input_boolean', 'media_player', 'cover', 'lock'].includes(entity.domain)
                    const isOn = entity.state === 'on' || entity.state === 'playing' || entity.state === 'locked' || entity.state === 'open'

                    return (
                      <div key={entity.entity_id} className={`ws-home-card ${isOn ? 'active' : ''}`}>
                        <div className="ws-home-card-header">
                          <span className="ws-home-card-icon">{domainIcon(entity.domain, entity.state)}</span>
                          <span className="ws-home-card-state">{entity.state}</span>
                        </div>
                        <div className="ws-home-card-info">
                          <strong title={entity.name}>{entity.name}</strong>
                          <small>{entity.domain}</small>
                        </div>
                        <div className="ws-home-card-actions">
                          {isToggleable && (
                            <button
                              type="button"
                              className={`ws-home-toggle-btn ${isOn ? 'on' : ''}`}
                              onClick={() => handleAction('toggle', entity.entity_id, entity.name)}
                              disabled={isBusy}
                            >
                              {isOn ? <ToggleRight size={16} /> : <ToggleLeft size={16} />}
                              <span>{isOn ? 'Ligado' : 'Desligado'}</span>
                            </button>
                          )}
                          {isScene && (
                            <button
                              type="button"
                              className="ws-home-exec-btn"
                              onClick={() => handleAction('run_scene', entity.entity_id, entity.name)}
                              disabled={isBusy}
                            >
                              <Play size={12} />
                              <span>Ativar cena</span>
                            </button>
                          )}
                          {isScript && (
                            <button
                              type="button"
                              className="ws-home-exec-btn"
                              onClick={() => handleAction('run_script', entity.entity_id, entity.name)}
                              disabled={isBusy}
                            >
                              <Play size={12} />
                              <span>Executar script</span>
                            </button>
                          )}
                        </div>
                      </div>
                    )
                  })}
                </div>
              </section>
            )
          })}
        </div>
      )}
    </div>
  )
}

