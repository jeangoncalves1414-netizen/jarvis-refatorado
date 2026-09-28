import { useState, useEffect } from 'react'

type VaultSearchResult = {
  file: string
  path: string
  matches: number
  snippet: string
  modified: number
}

export function VaultPanel() {
  const [dailyNote, setDailyNote] = useState('')
  const [userProfile, setUserProfile] = useState('')
  const [searchQuery, setSearchQuery] = useState('')
  const [searchResults, setSearchResults] = useState<VaultSearchResult[]>([])
  const [newFact, setNewFact] = useState('')
  const [newLogEntry, setNewLogEntry] = useState('')
  const [logCategory, setLogCategory] = useState('Atividade')
  const [activeTab, setActiveTab] = useState<'daily' | 'profile' | 'search'>('daily')
  const [status, setStatus] = useState('')

  useEffect(() => {
    loadDailyNote()
    loadProfile()
  }, [])

  const loadDailyNote = async () => {
    try {
      const res = await fetch('/api/vault/daily')
      const data = await res.json()
      setDailyNote(data.content || '')
    } catch {}
  }

  const loadProfile = async () => {
    try {
      const res = await fetch('/api/vault/profile')
      const data = await res.json()
      setUserProfile(data.content || '')
    } catch {}
  }

  const handleSearch = async () => {
    if (!searchQuery.trim()) return
    try {
      const res = await fetch(`/api/vault/search?q=${encodeURIComponent(searchQuery)}`)
      const data = await res.json()
      setSearchResults(data.results || [])
    } catch {}
  }

  const handleAddLog = async () => {
    if (!newLogEntry.trim()) return
    try {
      const res = await fetch('/api/vault/daily/log', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ entry: newLogEntry, category: logCategory }),
      })
      const data = await res.json()
      if (data.ok) {
        setNewLogEntry('')
        setStatus('✅ Entrada registrada no diário!')
        loadDailyNote()
        setTimeout(() => setStatus(''), 3000)
      }
    } catch {}
  }

  const handleAddFact = async () => {
    if (!newFact.trim()) return
    try {
      const res = await fetch('/api/vault/profile/fact', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ fact: newFact }),
      })
      const data = await res.json()
      if (data.ok) {
        setNewFact('')
        setStatus('✅ Fato adicionado ao seu perfil!')
        loadProfile()
        setTimeout(() => setStatus(''), 3000)
      }
    } catch {}
  }

  return (
    <div className="vault-panel">
      <div className="vault-header">
        <h3>📑 Memory Vault</h3>
        <p className="vault-subtitle">Memória persistente em Markdown · Diários · Perfil · AI Priming</p>
      </div>

      <div className="vault-tabs">
        <button id="vault-tab-daily" type="button" className={activeTab === 'daily' ? 'vault-tab-active' : 'vault-tab'} onClick={() => setActiveTab('daily')}>
          📅 Diário de Hoje
        </button>
        <button id="vault-tab-profile" type="button" className={activeTab === 'profile' ? 'vault-tab-active' : 'vault-tab'} onClick={() => setActiveTab('profile')}>
          👤 Meu Perfil
        </button>
        <button id="vault-tab-search" type="button" className={activeTab === 'search' ? 'vault-tab-active' : 'vault-tab'} onClick={() => setActiveTab('search')}>
          🔍 Buscar no Vault
        </button>
      </div>

      {status && <p className="vault-status">{status}</p>}

      {activeTab === 'daily' && (
        <div className="vault-tab-content">
          <div className="vault-log-composer">
            <textarea
              id="vault-log-entry"
              value={newLogEntry}
              onChange={e => setNewLogEntry(e.target.value)}
              placeholder="Registre uma atividade, aprendizado ou tarefa de hoje..."
              rows={3}
              className="vault-textarea"
            />
            <div className="vault-log-controls">
              <select id="vault-log-category" value={logCategory} onChange={e => setLogCategory(e.target.value)} className="vault-select">
                <option value="Atividade">Atividade</option>
                <option value="Aprendizado">Aprendizado</option>
                <option value="Decisão">Decisão</option>
                <option value="Pendência">Pendência</option>
                <option value="Ideia">Ideia</option>
              </select>
              <button id="vault-log-submit" type="button" className="vault-btn-primary" onClick={handleAddLog}>
                + Registrar no Diário
              </button>
            </div>
          </div>
          <div className="vault-note-content">
            <pre className="vault-markdown">{dailyNote || 'Carregando...'}</pre>
          </div>
        </div>
      )}

      {activeTab === 'profile' && (
        <div className="vault-tab-content">
          <div className="vault-log-composer">
            <input
              id="vault-profile-fact"
              type="text"
              value={newFact}
              onChange={e => setNewFact(e.target.value)}
              placeholder="Adicionar preferência ou fato sobre você (ex: Prefere código TypeScript a JavaScript)"
              className="vault-input"
            />
            <button id="vault-profile-submit" type="button" className="vault-btn-primary" onClick={handleAddFact}>
              + Adicionar ao Perfil
            </button>
          </div>
          <div className="vault-note-content">
            <pre className="vault-markdown">{userProfile || 'Carregando...'}</pre>
          </div>
        </div>
      )}

      {activeTab === 'search' && (
        <div className="vault-tab-content">
          <div className="vault-search-bar">
            <input
              id="vault-search-input"
              type="text"
              value={searchQuery}
              onChange={e => setSearchQuery(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && handleSearch()}
              placeholder="Pesquisar em notas, diários e documentos do Vault..."
              className="vault-input"
            />
            <button id="vault-search-submit" type="button" className="vault-btn-primary" onClick={handleSearch}>
              🔍 Pesquisar
            </button>
          </div>
          <div className="vault-results">
            {searchResults.length === 0 ? (
              <p className="vault-empty">Nenhum resultado. Tente outro termo.</p>
            ) : (
              searchResults.map((result, i) => (
                <div key={i} className="vault-result-item">
                  <span className="vault-result-file">📄 {result.file}</span>
                  <span className="vault-result-matches">{result.matches} ocorrência(s)</span>
                  <p className="vault-result-snippet">{result.snippet}</p>
                </div>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  )
}
