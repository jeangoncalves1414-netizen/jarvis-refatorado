import { useState, useEffect } from 'react'

type ForgedTool = {
  name: string
  filename: string
  path: string
  size: number
}

type ToolForgeModalProps = {
  isOpen?: boolean
  onClose: () => void
}

export function ToolForgeModal({ isOpen = true, onClose }: ToolForgeModalProps) {
  if (isOpen === false) return null

  const [toolName, setToolName] = useState('')
  const [description, setDescription] = useState('')
  const [generatedCode, setGeneratedCode] = useState('')
  const [installedTools, setInstalledTools] = useState<ForgedTool[]>([])
  const [status, setStatus] = useState<'idle' | 'generating' | 'validating' | 'installing' | 'done' | 'error'>('idle')
  const [message, setMessage] = useState('')

  useEffect(() => {
    loadInstalledTools()
  }, [])

  const loadInstalledTools = async () => {
    try {
      const res = await fetch('/api/tool-forge')
      const data = await res.json()
      setInstalledTools(data.tools || [])
    } catch {}
  }

  const handleGenerate = async () => {
    if (!toolName.trim() || !description.trim()) {
      setMessage('Preencha o nome e a descrição da ferramenta.')
      return
    }
    setStatus('generating')
    setMessage('Gerando código da ferramenta com o LLM...')
    try {
      // Build template directly without LLM (self-contained) for robustness
      const cleanName = toolName.toLowerCase().replace(/[^a-z0-9_]/g, '_')
      const className = toolName.split(/[\s_-]/).map(p => p.charAt(0).toUpperCase() + p.slice(1)).join('') + 'Tool'
      const code = `"""Ferramenta '${toolName}' gerada pelo Tool Forge.\nDescrição: ${description}\n"""\nfrom __future__ import annotations\nfrom typing import Any\nfrom app.agent.tools.base import BaseTool\n\n\nclass ${className}(BaseTool):\n    name = "${cleanName}"\n    description = "${description.replace(/"/g, "'")}"\n\n    def run(self, **kwargs: Any) -> dict[str, Any]:\n        # TODO: implementar a lógica aqui\n        return {"success": True, "message": "Ferramenta '${toolName}' executada com sucesso."}\n`
      setGeneratedCode(code)
      setStatus('validating')
      setMessage('Código gerado! Revise e clique em Instalar para ativar.')
    } catch (e: any) {
      setStatus('error')
      setMessage(`Erro ao gerar: ${e.message}`)
    }
  }

  const handleInstall = async () => {
    if (!generatedCode.trim()) return
    setStatus('installing')
    setMessage('Instalando ferramenta...')
    try {
      const res = await fetch('/api/tool-forge/install', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ tool_name: toolName, code: generatedCode }),
      })
      const data = await res.json()
      if (data.ok) {
        setStatus('done')
        setMessage(`✅ ${data.message}`)
        await loadInstalledTools()
      } else {
        setStatus('error')
        setMessage(`❌ ${data.message || 'Falha na instalação.'}`)
      }
    } catch (e: any) {
      setStatus('error')
      setMessage(`Erro: ${e.message}`)
    }
  }

  return (
    <div className="tool-forge-backdrop" onClick={onClose}>
      <div className="tool-forge-modal" onClick={e => e.stopPropagation()}>
        <div className="tool-forge-header">
          <div>
            <span className="tool-forge-icon">🛠️</span>
            <h2>Tool Forge</h2>
            <p className="tool-forge-subtitle">Crie e instale ferramentas personalizadas para o Jarvis</p>
          </div>
          <button id="tool-forge-close" type="button" className="tool-forge-close" onClick={onClose}>✕</button>
        </div>

        <div className="tool-forge-body">
          {/* Generator */}
          <div className="tool-forge-section">
            <h3>⚡ Nova Ferramenta</h3>
            <div className="tool-forge-form">
              <input
                id="tool-forge-name"
                type="text"
                placeholder="Nome da ferramenta (ex: consulta_clima)"
                value={toolName}
                onChange={e => setToolName(e.target.value)}
                className="tool-forge-input"
              />
              <textarea
                id="tool-forge-description"
                placeholder="Descreva o que esta ferramenta deve fazer..."
                value={description}
                onChange={e => setDescription(e.target.value)}
                className="tool-forge-textarea"
                rows={3}
              />
              <button
                id="tool-forge-generate"
                type="button"
                className="tool-forge-btn-primary"
                onClick={handleGenerate}
                disabled={status === 'generating'}
              >
                {status === 'generating' ? '⏳ Gerando...' : '✨ Gerar Código'}
              </button>
            </div>

            {generatedCode && (
              <div className="tool-forge-preview">
                <div className="tool-forge-preview-header">
                  <span>📄 Código Gerado — Revise antes de instalar</span>
                  <button
                    id="tool-forge-install"
                    type="button"
                    className="tool-forge-btn-success"
                    onClick={handleInstall}
                    disabled={status === 'installing'}
                  >
                    {status === 'installing' ? '⏳ Instalando...' : '🚀 Instalar'}
                  </button>
                </div>
                <textarea
                  value={generatedCode}
                  onChange={e => setGeneratedCode(e.target.value)}
                  className="tool-forge-code"
                  rows={14}
                  spellCheck={false}
                />
              </div>
            )}

            {message && (
              <p className={`tool-forge-message ${status === 'error' ? 'tool-forge-message-error' : status === 'done' ? 'tool-forge-message-success' : ''}`}>
                {message}
              </p>
            )}
          </div>

          {/* Installed Tools */}
          <div className="tool-forge-section">
            <h3>📦 Ferramentas Instaladas ({installedTools.length})</h3>
            {installedTools.length === 0 ? (
              <p className="tool-forge-empty">Nenhuma ferramenta customizada instalada ainda.</p>
            ) : (
              <div className="tool-forge-list">
                {installedTools.map(tool => (
                  <div key={tool.name} className="tool-forge-item">
                    <span className="tool-forge-item-name">🔧 {tool.name}</span>
                    <span className="tool-forge-item-meta">{tool.filename} · {(tool.size / 1024).toFixed(1)} KB</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
