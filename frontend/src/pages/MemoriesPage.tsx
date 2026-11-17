import { autoAllows } from '../components/AutoApprovals'
import { useState } from 'react'
import type { IdentityProfile, Memory, ProfileMemory } from '../types'
import { VaultPanel } from '../components/VaultPanel'
import { IdentityPage } from './IdentityPage'
import { CitedMemoriesPanel } from '../components/CitedMemoriesPanel'
import { isMobileStandalone } from '../hooks/useDirectChat'

type MemoriesPageProps = {
  memories: Memory[]
  memoryCollection: 'cited' | 'conversations' | 'user_memory' | 'profile_memory' | 'vault' | 'identity'
  notice: string
  identityProfiles: IdentityProfile[]
  selectedProfileId: string
  profileMemories: ProfileMemory[]
  onRefresh: () => void
  onClearTechnical: () => void
  onSelectCollection: (collection: any) => void
  onSelectProfile: (profileId: string) => void
  onRefreshProfile: () => void
  onAddProfileMemory: (text: string, kind: string, password: string) => Promise<boolean>
  onDeleteProfileMemory: (memoryId: string, password: string) => Promise<boolean>
  onClearProfileMemory: (password: string) => Promise<boolean>
}

export function MemoriesPage({
  memories,
  memoryCollection,
  notice,
  identityProfiles,
  selectedProfileId,
  profileMemories,
  onRefresh,
  onClearTechnical,
  onSelectCollection,
  onSelectProfile,
  onRefreshProfile,
  onAddProfileMemory,
  onDeleteProfileMemory,
  onClearProfileMemory,
}: MemoriesPageProps) {
  const mobile = isMobileStandalone()
  const [newMemory, setNewMemory] = useState('')
  const [memoryKind, setMemoryKind] = useState('note')
  const [password, setPassword] = useState('')

  const submitMemory = async () => {
    if (!newMemory.trim() || !password || !selectedProfileId) return
    if (await onAddProfileMemory(newMemory, memoryKind, password)) {
      setNewMemory('')
      setPassword('')
    }
  }

  const clearProfile = async () => {
    if (!password || !selectedProfileId || !await autoAllows('bulk') && !window.confirm('Apagar todas as memórias deste perfil?')) return
    if (await onClearProfileMemory(password)) setPassword('')
  }

  return (
    <section className="memories-card">
      <div className="section-heading">
        <div>
          <p className="eyebrow">MEMÓRIA SEMÂNTICA</p>
          <h2>O que o Jarvis lembra</h2>
        </div>
        <div className="memory-actions">
          <button type="button" onClick={onRefresh}>Atualizar</button>
          <button type="button" onClick={onClearTechnical}>Limpar erros técnicos</button>
        </div>
      </div>
      <div className="memory-tabs">
        <button type="button" className={memoryCollection === 'cited' ? 'memory-tab-active' : ''} onClick={() => onSelectCollection('cited')}>Com fonte</button>
        {(['conversations', 'user_memory'] as const).map(collection => (
          <button key={collection} type="button" className={memoryCollection === collection ? 'memory-tab-active' : ''} onClick={() => onSelectCollection(collection)}>
            {collection === 'conversations' ? 'Conversas globais' : 'Sobre você'}
          </button>
        ))}
        {!mobile && <button type="button" className={memoryCollection === 'profile_memory' ? 'memory-tab-active' : ''} onClick={() => onSelectCollection('profile_memory')}>Por pessoa</button>}
        <button type="button" className={memoryCollection === 'vault' ? 'memory-tab-active' : ''} onClick={() => onSelectCollection('vault')}>📑 Vault & Diários</button>
        {!mobile && <button type="button" className={memoryCollection === 'identity' ? 'memory-tab-active' : ''} onClick={() => onSelectCollection('identity')}>👤 Perfis Biométricos & Câmera</button>}
      </div>
      {notice && <p className="settings-notice">{notice}</p>}

      {memoryCollection === 'cited' ? (
        <CitedMemoriesPanel />
      ) : !mobile && memoryCollection === 'identity' ? (
        <IdentityPage />
      ) : memoryCollection === 'vault' ? (
        <VaultPanel />
      ) : !mobile && memoryCollection === 'profile_memory' ? (
        <div className="profile-memory-panel">
          <div className="profile-memory-toolbar">
            <select value={selectedProfileId} onChange={event => onSelectProfile(event.target.value)} aria-label="Perfil da memória">
              <option value="">Selecione uma pessoa</option>
              {identityProfiles.map(profile => <option key={profile.id} value={profile.id}>{profile.name} · {profile.role || 'usuário'}</option>)}
            </select>
            <button type="button" disabled={!selectedProfileId} onClick={onRefreshProfile}>Atualizar</button>
          </div>
          {selectedProfileId && <>
            <div className="profile-memory-composer">
              <textarea value={newMemory} onChange={event => setNewMemory(event.target.value)} placeholder="Adicionar uma memória privada para esta pessoa…" />
              <div className="profile-memory-fields"><select value={memoryKind} onChange={event => setMemoryKind(event.target.value)}><option value="note">Nota</option><option value="fact">Fato</option><option value="preference">Preferência</option></select><input type="password" value={password} onChange={event => setPassword(event.target.value)} placeholder="Senha do perfil" /><button type="button" disabled={!newMemory.trim() || !password} onClick={submitMemory}>Salvar memória</button></div>
              <small>Memórias por pessoa ficam separadas e só entram no chat quando esse perfil é reconhecido.</small>
            </div>
            <div className="profile-memory-danger"><input type="password" value={password} onChange={event => setPassword(event.target.value)} placeholder="Senha para apagar" /><button type="button" onClick={clearProfile}>Apagar memórias do perfil</button></div>
            <div className="memory-list">{profileMemories.length ? profileMemories.map(memory => <article key={memory.id}><span>{memory.kind || 'nota'} · {memory.updated_at ? new Date(memory.updated_at * 1000).toLocaleString('pt-BR') : 'memória privada'}</span><p>{memory.text}</p><button type="button" onClick={async () => { if (password && await onDeleteProfileMemory(memory.id, password)) setPassword('') }}>Excluir</button></article>) : <p className="empty-state">Este perfil ainda não tem memórias privadas.</p>}</div>
          </>}
        </div>
      ) : memories.length ? (
        <div className="memory-list">{memories.map((memory, index) => <article key={memory.id || index}><span>{memory.metadata?.timestamp ? new Date(Number(memory.metadata.timestamp) * 1000).toLocaleString('pt-BR') : memoryCollection === 'conversations' ? 'CONVERSA' : 'MEMÓRIA'}</span><p>{memory.text || 'Memória sem conteúdo.'}</p></article>)}</div>
      ) : <p className="empty-state">Nenhuma memória nesta coleção.</p>}
    </section>
  )
}
