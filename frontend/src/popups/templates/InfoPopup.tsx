import { StaggerList } from '../motion'
import type { InfoPopupData, PopupComponentProps } from '../registry'

// Aviso curto: só texto vindo do agente (nenhum número calculado). As linhas entram em sequência.
export function InfoPopup({ popup, revision }: PopupComponentProps<InfoPopupData>) {
  const items = popup.data.lines.map((text, index) => ({ id: `${revision}-${index}`, text }))
  return (
    <div className="ws-popup-info">
      {items.length > 0 && (
        <StaggerList
          items={items}
          getId={item => item.id}
          newIds={items.map(item => item.id)}
          intervalMs={120}
          renderItem={item => <span>{item.text}</span>}
        />
      )}
    </div>
  )
}
