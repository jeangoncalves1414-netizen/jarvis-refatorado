import { useEffect, useState } from 'react'

type StudyDialogProps = {
  open: boolean
  title: string
  description?: string
  kind?: 'confirm' | 'text' | 'category'
  initialValue?: string
  initialColor?: string
  confirmLabel?: string
  onClose: () => void
  onSubmit: (value: string, color?: string) => void
}

const COLORS = ['#b9ef63', '#00daf8', '#a78bfa', '#fb7185', '#fb923c', '#facc15', '#34d399', '#60a5fa', '#f472b6', '#c084fc']

export function StudyDialog({ open, title, description, kind = 'confirm', initialValue = '', initialColor = COLORS[0], confirmLabel = 'Confirmar', onClose, onSubmit }: StudyDialogProps) {
  const [value, setValue] = useState(initialValue)
  const [color, setColor] = useState(initialColor)
  useEffect(() => { if (open) { setValue(initialValue); setColor(initialColor) } }, [open, initialValue, initialColor])
  if (!open) return null
  return <div className="study-dialog-backdrop" role="presentation" onMouseDown={event => { if (event.currentTarget === event.target) onClose() }}>
    <div className="study-dialog" role="dialog" aria-modal="true" aria-labelledby="study-dialog-title">
      <div className="study-dialog-icon">{kind === 'category' ? '✦' : kind === 'text' ? '✎' : '!'}</div>
      <div className="study-dialog-copy"><h3 id="study-dialog-title">{title}</h3>{description && <p>{description}</p>}</div>
      {kind !== 'confirm' && <input autoFocus className="study-dialog-input" value={value} onChange={event => setValue(event.target.value)} onKeyDown={event => { if (event.key === 'Enter' && value.trim()) onSubmit(value.trim(), kind === 'category' ? color : undefined); if (event.key === 'Escape') onClose() }} placeholder={kind === 'category' ? 'Nome da categoria' : 'Nome da sessão'} />}
      {kind === 'category' && <div className="study-color-palette" aria-label="Paleta de cores">{COLORS.map(item => <button key={item} type="button" aria-label={`Usar cor ${item}`} className={color === item ? 'selected' : ''} style={{ backgroundColor: item }} onClick={() => setColor(item)} />)}</div>}
      <div className="study-dialog-actions"><button type="button" className="study-dialog-cancel" onClick={onClose}>Cancelar</button><button type="button" className="study-dialog-submit" disabled={kind !== 'confirm' && !value.trim()} onClick={() => onSubmit(value.trim(), kind === 'category' ? color : undefined)}>{confirmLabel}</button></div>
    </div>
  </div>
}
