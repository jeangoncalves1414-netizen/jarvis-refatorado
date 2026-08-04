import { forwardRef } from 'react';

type BackgroundPatternProps = {
  variant: 'dots' | 'grid'
  mask?: 'fade-edges' | 'fade-center' | 'none'
  parallax?: boolean
}

export const BackgroundPattern = forwardRef<HTMLDivElement, BackgroundPatternProps>(
  ({ variant, mask = 'fade-edges', parallax = false }, ref) => {
  const fill = 'rgba(0, 218, 248, 0.12)'
  const backgroundImage = variant === 'dots'
    ? `radial-gradient(${fill} 1px, transparent 1.2px)`
    : `linear-gradient(to right, ${fill} 1px, transparent 1px), linear-gradient(to bottom, ${fill} 1px, transparent 1px)`

  return <div
    aria-hidden="true"
    className={`camera-bg-pattern camera-bg-${mask}${parallax ? ' camera-bg-parallax' : ''}`}
    ref={ref}
    style={{ backgroundImage, backgroundSize: '28px 28px' }}
  />
}
)
