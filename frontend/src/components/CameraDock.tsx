import { useState, type CSSProperties } from 'react'

type CameraDockProps = {
  resizing: boolean
  onResize: () => void
  onRename: () => void
  onFocus: () => void
  onAnalyze: () => void
}

const actions = [
  { label: 'Redimensionar', icon: '↘', key: 'onResize' },
  { label: 'Renomear', icon: '✎', key: 'onRename' },
  { label: 'Destacar', icon: '⛶', key: 'onFocus' },
  { label: 'Analisar agora', icon: '◉', key: 'onAnalyze' },
] as const

export function CameraDock(props: CameraDockProps) {
  const [hovered, setHovered] = useState<number | null>(null)

  return <div className="camera-dock" role="toolbar" aria-label="Opções da câmera selecionada" onPointerDown={event => event.stopPropagation()}>
    {actions.map((action, index) => {
      const callback = props[action.key]
      return <button
        className="camera-dock-item"
        key={action.key}
        type="button"
        aria-label={action.label}
        onClick={event => { event.stopPropagation(); callback() }}
        onMouseEnter={() => setHovered(index)}
        onMouseLeave={() => setHovered(null)}
        style={{ '--dock-size': hovered === index ? '52px' : '38px' } as CSSProperties}
      >
        {hovered === index && <span className="camera-dock-label">{action.key === 'onResize' && props.resizing ? 'Concluir redimensionamento' : action.label}</span>}
        <span>{action.icon}</span>
      </button>
    })}
  </div>
}
