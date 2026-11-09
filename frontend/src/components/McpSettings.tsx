import { useEffect, useState } from 'react'
import {
  Server,
  Plus,
  RefreshCw,
  Trash2,
  Check,
  AlertCircle,
  Terminal,
  ChevronDown,
  ChevronRight,
  Wrench,
  ShieldAlert,
  ShieldCheck,
  Power,
  X,
} from 'lucide-react'
import { Switch } from './Switch'

export type MCPServer = {
  id: string
  name: string
  command: string
  args: string[]
  env: Record<string, string>
  enabled: boolean
  status: 'online' | 'offline' | 'error' | 'disabled' | 'connecting'
  error?: string
  tools_count: number
}

export type MCPTool = {
  server_id: string
  server_name: string
  name: string
  raw_name: string
  description: string
  parameters: Record<string, unknown>
  risk: 'observe' | 'low' | 'high' | 'critical'
  requires_confirmation: boolean
}

export function McpSettings() {
  const [servers, setServers] = useState<MCPServer[]>([])
  const [tools, setTools] = useState<MCPTool[]>([])
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [errorMsg, setErrorMsg] = useState<string | null>(null)
  const [successMsg, setSuccessMsg] = useState<string | null>(null)

  // Expansão de ferramentas por servidor
  const [expandedServerId, setExpandedServerId] = useState<string | null>(null)

  // Modal / Formulário de adicionar servidor
  const [showForm, setShowForm] = useState(false)
  const [formId, setFormId] = useState('')
  const [formName, setFormName] = useState('')
  const [formCommand, setFormCommand] = useState('')
  const [formArgs, setFormArgs] = useState('')
  const [formEnv, setFormEnv] = useState('')
  const [saving, setSaving] = useState(false)

  const loadData = async (silent = false) => {
    if (!silent) setLoading(true)
    else setRefreshing(true)
    setErrorMsg(null)
    try {
      const [resServers, resTools] = await Promise.all([
        fetch('/api/mcp/servers'),
        fetch('/api/mcp/tools'),
      ])

      if (resServers.ok) {
        const data = await resServers.json()
        if (data.ok && Array.isArray(data.servers)) {
          setServers(data.servers)
        }
      }

      if (resTools.ok) {
        const data = await resTools.json()
        if (data.ok && Array.isArray(data.tools)) {
          setTools(data.tools)
        }
      }
    } catch (err) {
      setErrorMsg(err instanceof Error ? err.message : 'Falha ao conectar à API MCP.')
    } finally {
      setLoading(false)
      setRefreshing(false)
    }
  }

  useEffect(() => {
    loadData()
  }, [])

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!formCommand.trim()) {
      setErrorMsg('O comando executável é obrigatório.')
      return
    }

    setSaving(true)
    setErrorMsg(null)
    setSuccessMsg(null)

    try {
      // Parse de argumentos (suporta quebras de linha ou espaços)
      const parsedArgs = formArgs
        .split('\n')
        .flatMap(line => line.trim().split(/\s+/))
        .filter(Boolean)

      // Parse de variáveis de ambiente KEY=VALUE
      const parsedEnv: Record<string, string> = {}
      if (formEnv.trim()) {
        formEnv.split('\n').forEach(line => {
          const idx = line.indexOf('=')
          if (idx > 0) {
            const k = line.slice(0, idx).trim()
            const v = line.slice(idx + 1).trim()
            if (k) parsedEnv[k] = v
          }
        })
      }

      const payload = {
        id: formId.trim() || undefined,
        name: formName.trim() || undefined,
        command: formCommand.trim(),
        args: parsedArgs,
        env: parsedEnv,
        enabled: true,
      }

      const res = await fetch('/api/mcp/servers', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })

      const data = await res.json()
      if (!res.ok || !data.ok) {
        throw new Error(data.error || 'Erro ao salvar servidor MCP.')
      }

      setSuccessMsg(`Servidor '${payload.name || payload.command}' adicionado com sucesso!`)
      setShowForm(false)
      setFormId('')
      setFormName('')
      setFormCommand('')
      setFormArgs('')
      setFormEnv('')
      await loadData(true)
    } catch (err) {
      setErrorMsg(err instanceof Error ? err.message : 'Erro ao salvar servidor.')
    } finally {
      setSaving(false)
    }
  }

  const handleToggle = async (server: MCPServer) => {
    setErrorMsg(null)
    try {
      const res = await fetch(`/api/mcp/servers/${server.id}/toggle`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ enabled: !server.enabled }),
      })
      const data = await res.json()
      if (!res.ok || !data.ok) {
        throw new Error(data.error || 'Erro ao alterar estado do servidor.')
      }
      await loadData(true)
    } catch (err) {
      setErrorMsg(err instanceof Error ? err.message : 'Erro ao alterar servidor.')
    }
  }

  const handleRestart = async (serverId: string) => {
    setErrorMsg(null)
    setRefreshing(true)
    try {
      const res = await fetch(`/api/mcp/servers/${serverId}/restart`, {
        method: 'POST',
      })
      const data = await res.json()
      if (!res.ok || !data.ok) {
        throw new Error(data.error || 'Erro ao reiniciar servidor MCP.')
      }
      setSuccessMsg(`Servidor '${serverId}' reiniciado com sucesso.`)
      await loadData(true)
    } catch (err) {
      setErrorMsg(err instanceof Error ? err.message : 'Erro ao reiniciar servidor.')
    } finally {
      setRefreshing(false)
    }
  }

  const handleDelete = async (serverId: string, serverName: string) => {
    if (!window.confirm(`Deseja realmente remover o servidor MCP '${serverName}'?`)) {
      return
    }
    setErrorMsg(null)
    try {
      const res = await fetch(`/api/mcp/servers/${serverId}`, {
        method: 'DELETE',
      })
      const data = await res.json()
      if (!res.ok || !data.ok) {
        throw new Error(data.error || 'Erro ao excluir servidor.')
      }
      setSuccessMsg(`Servidor '${serverName}' removido com sucesso.`)
      await loadData(true)
    } catch (err) {
      setErrorMsg(err instanceof Error ? err.message : 'Erro ao excluir servidor.')
    }
  }

  const getStatusBadge = (server: MCPServer) => {
    if (!server.enabled) {
      return (
        <span style={{ fontSize: 11, padding: '2px 8px', borderRadius: 999, background: 'rgba(255,255,255,0.06)', color: 'var(--text-muted)' }}>
          Desativado
        </span>
      )
    }
    switch (server.status) {
      case 'online':
        return (
          <span style={{ fontSize: 11, padding: '2px 8px', borderRadius: 999, background: 'rgba(34, 197, 94, 0.15)', color: '#4ade80', display: 'inline-flex', alignItems: 'center', gap: 4 }}>
            <span style={{ width: 6, height: 6, borderRadius: '50%', background: '#4ade80' }} />
            Online ({server.tools_count} ferramentas)
          </span>
        )
      case 'connecting':
        return (
          <span style={{ fontSize: 11, padding: '2px 8px', borderRadius: 999, background: 'rgba(234, 179, 8, 0.15)', color: '#facc15' }}>
            Conectando...
          </span>
        )
      case 'error':
        return (
          <span style={{ fontSize: 11, padding: '2px 8px', borderRadius: 999, background: 'rgba(239, 68, 68, 0.15)', color: '#f87171', display: 'inline-flex', alignItems: 'center', gap: 4 }}>
            <AlertCircle size={12} />
            Erro de Conexão
          </span>
        )
      default:
        return (
          <span style={{ fontSize: 11, padding: '2px 8px', borderRadius: 999, background: 'rgba(255,255,255,0.06)', color: 'var(--text-muted)' }}>
            Offline
          </span>
        )
    }
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      {/* Cabeçalho */}
      <article className="settings-card">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: 12 }}>
          <div>
            <p className="eyebrow">EXTENSÕES DE PROTOCOLO</p>
            <h2 style={{ display: 'flex', alignItems: 'center', gap: 8, margin: '4px 0 8px' }}>
              <Server size={20} color="#00daf8" />
              Servidores MCP (Model Context Protocol)
            </h2>
            <p style={{ margin: 0, color: 'var(--text-secondary)', fontSize: 13, maxWidth: 640 }}>
              Conecte ferramentas externas como GitHub, PostgreSQL, Sistemas de Arquivos ou servidores customizados via stdio. As ferramentas descobertas são integradas automaticamente ao Action Kernel do Jarvis.
            </p>
          </div>
          <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
            <button
              type="button"
              className="outline-button"
              onClick={() => loadData(true)}
              disabled={refreshing}
              title="Atualizar servidores e ferramentas"
              style={{ display: 'inline-flex', alignItems: 'center', gap: 6, padding: '8px 12px' }}
            >
              <RefreshCw size={14} className={refreshing ? 'animate-spin' : ''} />
              Atualizar
            </button>
            <button
              type="button"
              className="outline-button"
              onClick={() => setShowForm(!showForm)}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: 6,
                padding: '8px 14px',
                background: 'rgba(0, 218, 248, 0.12)',
                borderColor: 'rgba(0, 218, 248, 0.4)',
                color: '#00daf8',
                fontWeight: 600,
              }}
            >
              {showForm ? <X size={14} /> : <Plus size={14} />}
              {showForm ? 'Fechar' : 'Novo Servidor'}
            </button>
          </div>
        </div>

        {/* Mensagens de Alerta */}
        {errorMsg && (
          <div style={{ marginTop: 12, padding: '10px 14px', borderRadius: 8, background: 'rgba(239, 68, 68, 0.12)', border: '1px solid rgba(239, 68, 68, 0.3)', color: '#fca5a5', fontSize: 13, display: 'flex', alignItems: 'center', gap: 8 }}>
            <AlertCircle size={16} />
            <span>{errorMsg}</span>
          </div>
        )}
        {successMsg && (
          <div style={{ marginTop: 12, padding: '10px 14px', borderRadius: 8, background: 'rgba(34, 197, 94, 0.12)', border: '1px solid rgba(34, 197, 94, 0.3)', color: '#86efac', fontSize: 13, display: 'flex', alignItems: 'center', gap: 8 }}>
            <Check size={16} />
            <span>{successMsg}</span>
          </div>
        )}

        {/* Formulário de Adicionar Servidor */}
        {showForm && (
          <form onSubmit={handleSave} style={{ marginTop: 16, padding: 16, borderRadius: 10, background: 'rgba(0,0,0,0.25)', border: '1px solid rgba(255,255,255,0.08)', display: 'flex', flexDirection: 'column', gap: 12 }}>
            <h3 style={{ margin: '0 0 4px', fontSize: 15, fontWeight: 700, color: 'var(--text-primary)' }}>
              Configurar Servidor MCP
            </h3>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
              <label className="field-label">
                Nome do Servidor
                <input
                  type="text"
                  placeholder="Ex: Arquivos Locais, GitHub, PostgreSQL"
                  value={formName}
                  onChange={e => setFormName(e.target.value)}
                />
              </label>
              <label className="field-label">
                Identificador (ID Único, opcional)
                <input
                  type="text"
                  placeholder="Ex: filesystem, github"
                  value={formId}
                  onChange={e => setFormId(e.target.value)}
                />
              </label>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 2fr', gap: 12 }}>
              <label className="field-label">
                Comando (Executável) *
                <input
                  type="text"
                  placeholder="npx, python, node, uvx"
                  value={formCommand}
                  onChange={e => setFormCommand(e.target.value)}
                  required
                />
              </label>
              <label className="field-label">
                Argumentos
                <input
                  type="text"
                  placeholder="-y @modelcontextprotocol/server-filesystem C:\Users\..."
                  value={formArgs}
                  onChange={e => setFormArgs(e.target.value)}
                />
              </label>
            </div>

            <label className="field-label">
              Variáveis de Ambiente (opcional, uma por linha: CHAVE=VALOR)
              <textarea
                rows={2}
                placeholder="GITHUB_TOKEN=ghp_...&#10;API_KEY=xyz"
                value={formEnv}
                onChange={e => setFormEnv(e.target.value)}
                style={{ width: '100%', resize: 'vertical', fontFamily: 'monospace', fontSize: 12 }}
              />
            </label>

            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8, marginTop: 4 }}>
              <button
                type="button"
                className="outline-button"
                onClick={() => setShowForm(false)}
                disabled={saving}
              >
                Cancelar
              </button>
              <button
                type="submit"
                className="outline-button"
                disabled={saving}
                style={{ background: 'var(--accent-blue, #00daf8)', color: '#000', fontWeight: 700 }}
              >
                {saving ? 'Conectando...' : 'Salvar e Conectar'}
              </button>
            </div>
          </form>
        )}
      </article>

      {/* Lista de Servidores */}
      <article className="settings-card">
        <p className="eyebrow">SERVIDORES CONFIGURADOS</p>
        <h2 style={{ margin: '4px 0 12px' }}>Conexões MCP Ativas</h2>

        {loading ? (
          <p style={{ color: 'var(--text-muted)', fontSize: 13 }}>Carregando servidores MCP...</p>
        ) : servers.length === 0 ? (
          <div style={{ textAlign: 'center', padding: '32px 16px', color: 'var(--text-muted)' }}>
            <Server size={36} style={{ opacity: 0.3, marginBottom: 8 }} />
            <p style={{ margin: '0 0 8px', fontSize: 14 }}>Nenhum servidor MCP configurado.</p>
            <p style={{ fontSize: 12, margin: 0, opacity: 0.7 }}>
              Clique em <strong>+ Novo Servidor</strong> acima para conectar suas ferramentas locais via stdio.
            </p>
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            {servers.map(server => {
              const serverTools = tools.filter(t => t.server_id === server.id)
              const isExpanded = expandedServerId === server.id

              return (
                <div
                  key={server.id}
                  style={{
                    borderRadius: 10,
                    border: '1px solid rgba(255,255,255,0.08)',
                    background: 'rgba(255,255,255,0.02)',
                    overflow: 'hidden',
                  }}
                >
                  {/* Cabeçalho do Card */}
                  <div
                    style={{
                      padding: '12px 16px',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      gap: 12,
                      flexWrap: 'wrap',
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: 12, minWidth: 200, flex: 1 }}>
                      <div
                        style={{
                          width: 36,
                          height: 36,
                          borderRadius: 8,
                          background: 'rgba(0, 218, 248, 0.08)',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          color: '#00daf8',
                        }}
                      >
                        <Terminal size={18} />
                      </div>
                      <div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                          <h4 style={{ margin: 0, fontSize: 14, fontWeight: 700, color: 'var(--text-primary)' }}>
                            {server.name}
                          </h4>
                          <span style={{ fontSize: 11, fontFamily: 'monospace', color: 'var(--text-muted)' }}>
                            ({server.id})
                          </span>
                        </div>
                        <div style={{ fontSize: 12, fontFamily: 'monospace', color: 'var(--text-secondary)', marginTop: 2 }}>
                          {server.command} {server.args.join(' ')}
                        </div>
                      </div>
                    </div>

                    <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                      {getStatusBadge(server)}

                      {/* Alternar Ativo/Inativo */}
                      <Switch
                        checked={server.enabled}
                        onChange={() => handleToggle(server)}
                        label=""
                        glowColor="green"
                      />

                      {/* Reiniciar */}
                      <button
                        type="button"
                        className="outline-button"
                        onClick={() => handleRestart(server.id)}
                        title="Reiniciar servidor"
                        style={{ padding: '6px 8px' }}
                      >
                        <RefreshCw size={13} />
                      </button>

                      {/* Excluir */}
                      <button
                        type="button"
                        className="outline-button"
                        onClick={() => handleDelete(server.id, server.name)}
                        title="Excluir servidor"
                        style={{ padding: '6px 8px', color: '#f87171', borderColor: 'rgba(239,68,68,0.2)' }}
                      >
                        <Trash2 size={13} />
                      </button>

                      {/* Expandir Ferramentas */}
                      <button
                        type="button"
                        className="outline-button"
                        onClick={() => setExpandedServerId(isExpanded ? null : server.id)}
                        style={{ display: 'inline-flex', alignItems: 'center', gap: 4, padding: '6px 10px', fontSize: 12 }}
                      >
                        <Wrench size={12} />
                        <span>{server.tools_count}</span>
                        {isExpanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                      </button>
                    </div>
                  </div>

                  {/* Mensagem de Erro do Servidor */}
                  {server.error && (
                    <div style={{ padding: '8px 16px', background: 'rgba(239, 68, 68, 0.08)', color: '#f87171', fontSize: 12, borderTop: '1px solid rgba(239, 68, 68, 0.2)' }}>
                      <strong>Falha de Conexão:</strong> {server.error}
                    </div>
                  )}

                  {/* Lista de Ferramentas Expandida */}
                  {isExpanded && (
                    <div style={{ borderTop: '1px solid rgba(255,255,255,0.06)', background: 'rgba(0,0,0,0.15)', padding: 16 }}>
                      <h5 style={{ margin: '0 0 10px', fontSize: 12, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--text-muted)' }}>
                        Ferramentas Expostas ao Action Kernel ({serverTools.length})
                      </h5>
                      {serverTools.length === 0 ? (
                        <p style={{ color: 'var(--text-muted)', fontSize: 12, margin: 0 }}>
                          Nenhuma ferramenta disponível no momento. Verifique se o servidor está online.
                        </p>
                      ) : (
                        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: 8 }}>
                          {serverTools.map(t => (
                            <div
                              key={t.name}
                              style={{
                                padding: '10px 12px',
                                borderRadius: 8,
                                background: 'rgba(255,255,255,0.03)',
                                border: '1px solid rgba(255,255,255,0.06)',
                                display: 'flex',
                                flexDirection: 'column',
                                gap: 4,
                              }}
                            >
                              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 6 }}>
                                <span style={{ fontFamily: 'monospace', fontWeight: 600, fontSize: 12, color: '#00daf8' }}>
                                  {t.name}
                                </span>
                                {t.risk === 'observe' ? (
                                  <span style={{ fontSize: 10, padding: '1px 6px', borderRadius: 4, background: 'rgba(34,197,94,0.15)', color: '#4ade80', display: 'inline-flex', alignItems: 'center', gap: 3 }}>
                                    <ShieldCheck size={10} /> Leitura
                                  </span>
                                ) : (
                                  <span style={{ fontSize: 10, padding: '1px 6px', borderRadius: 4, background: 'rgba(234,179,8,0.15)', color: '#facc15', display: 'inline-flex', alignItems: 'center', gap: 3 }}>
                                    <ShieldAlert size={10} /> Escrita
                                  </span>
                                )}
                              </div>
                              {t.description && (
                                <p style={{ margin: 0, fontSize: 11, color: 'var(--text-secondary)', lineHeight: 1.4 }}>
                                  {t.description}
                                </p>
                              )}
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        )}
      </article>
    </div>
  )
}
