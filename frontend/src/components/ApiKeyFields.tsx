import { useEffect, useRef } from 'react'
import { Plus, X } from 'lucide-react'

/** Keep the existing comma-separated wire format used by desktop rotation and cloud sync. */
export function ApiKeyFields({ provider, value, visible = false, onChange }: { provider: string; value: string; visible?: boolean; onChange: (value: string) => void }) {
  const keys = value.replace(/\n/g, ',').split(',')
  const list = useRef<HTMLDivElement>(null)
  useEffect(() => { if (list.current) list.current.scrollTop = list.current.scrollHeight }, [keys.length])
  return <div style={{ display: 'grid', gap: 8, flex: 1, minWidth: 0 }}>
    <div ref={list} role="group" aria-label={`Chaves de ${provider}`} style={{ display: 'grid', gap: 8, maxHeight: 180, overflowY: 'auto', overscrollBehavior: 'contain' }}>
    {keys.map((key, index) => <div key={index} style={{ display: 'flex', gap: 6 }}>
      <input type={visible ? 'text' : 'password'} autoComplete="off" spellCheck={false} aria-label={`${provider} — chave ${index + 1}`} value={key.trim()}
        style={{ flex: 1, minWidth: 0 }} onChange={event => onChange(keys.map((v, i) => i === index ? event.target.value : v).join(','))} />
      {keys.length > 1 && <button type="button" className="outline-button" aria-label={`Remover chave ${index + 1} de ${provider}`} onClick={() => onChange(keys.filter((_, i) => i !== index).join(','))}><X size={14} /></button>}
    </div>)}
    </div>
    <button type="button" className="outline-button" aria-label={`Adicionar chave de ${provider}`} onClick={() => onChange(`${value},`)}><Plus size={14} /> Adicionar chave</button>
  </div>
}
