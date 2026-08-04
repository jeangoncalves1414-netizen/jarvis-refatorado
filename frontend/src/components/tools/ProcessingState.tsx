import { AiLoader } from '../AiLoader'

export type ProcessingStateProps = {
  label?: string
  sublabel?: string
  variant?: 'shimmer' | 'pulse' | 'dots'
  /** Show a sweeping loading-line beneath the label */
  showLine?: boolean
}

export function ProcessingState({
  label = 'Jarvis está pensando…',
  sublabel,
  showLine = true,
}: ProcessingStateProps) {
  return (
    <div className="ps-container ps-variant-shimmer">
      {/* Animated orb indicator */}
      <div className="ps-icon-wrapper">
        <div className="ps-orb-pulse" />
      </div>

      <div className="ps-content">
        {/* Shimmer text label */}
        <AiLoader variant="shimmer-text" text={label} />
        {sublabel && <span className="ps-sublabel">{sublabel}</span>}
        {/* Optional loading-line progress bar */}
        {showLine && <AiLoader variant="loading-line" className="ps-line" />}
      </div>

      {/* Bouncing dots on the right */}
      <AiLoader variant="dots" className="ps-dots-right" />
    </div>
  )
}
