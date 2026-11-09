import { CountUp, LiquidGauge } from '../motion'
import type { PopupComponentProps, WaterPopupData } from '../registry'

// Água de hoje: o nível sobe de previous_ml para current_ml contra a meta (valores do Life OS).

const ml = (value: number) => Math.round(value).toLocaleString('pt-BR')

export function WaterPopup({ popup }: PopupComponentProps<WaterPopupData>) {
  const { current_ml, previous_ml, target_ml, percentage } = popup.data
  const pctOf = (value: number) => target_ml > 0 ? (value / target_ml) * 100 : 0
  const fromPct = pctOf(previous_ml)
  const toPct = target_ml > 0 ? pctOf(current_ml) : 0
  const reached = target_ml > 0 && current_ml >= target_ml
  const delta = current_ml - previous_ml
  return (
    <div className="ws-popup-water">
      <LiquidGauge fromPct={fromPct} toPct={toPct} label={`${ml(current_ml)} de ${ml(target_ml)} ml, ${percentage} %`} targetLabel={`meta ${ml(target_ml)} ml`} />
      <div className="ws-popup-water-values">
        <p className="ws-popup-water-main"><CountUp from={previous_ml} to={current_ml} format={ml} /> de {ml(target_ml)} ml</p>
        <p className="ws-popup-water-pct"><CountUp from={Math.round(fromPct)} to={percentage} format={value => `${Math.round(value)}%`} /> da meta</p>
        {delta !== 0 && <p className="ws-popup-water-delta">{delta > 0 ? '+' : '−'}{ml(Math.abs(delta))} ml agora</p>}
        {!reached && target_ml > 0 && <p className="ws-popup-water-left">Faltam {ml(target_ml - current_ml)} ml</p>}
      </div>
    </div>
  )
}
