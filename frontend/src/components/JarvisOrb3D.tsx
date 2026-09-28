import { useEffect, useRef } from 'react'

export type AgentState = 'idle' | 'thinking' | 'streaming' | 'tool_executing' | 'celebrating'

type JarvisOrb3DProps = {
  size?: number
  listening?: boolean
  speaking?: boolean
  state?: AgentState
  className?: string
  interactive?: boolean
  onClick?: () => void
}

export function JarvisOrb3D({
  size = 140,
  listening = false,
  speaking = false,
  state = 'idle',
  className = '',
  interactive = false,
  onClick,
}: JarvisOrb3DProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const prevSpeakingRef = useRef(false)
  const answerAnimRef = useRef({ active: false, progress: 0 })

  // Trigger pulse whenever speaking starts
  useEffect(() => {
    if (speaking && !prevSpeakingRef.current) {
      answerAnimRef.current = { active: true, progress: 0 }
    }
    prevSpeakingRef.current = speaking
  }, [speaking])

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    if (!ctx) return

    const dpr = Math.min(window.devicePixelRatio || 1, 2)
    canvas.width = size * dpr
    canvas.height = size * dpr
    ctx.setTransform(1, 0, 0, 1, 0, 0)
    ctx.scale(dpr, dpr)

    const cx = size / 2
    const cy = size / 2
    const isSmall = size < 70

    // Core radii
    const coreR = size * 0.18
    const innerRingR = size * 0.28
    const outerRingR = size * 0.42
    const glowR = size * 0.46

    // Particles
    const particleCount = isSmall ? 8 : Math.min(32, Math.round(size * 0.16))
    const particles = Array.from({ length: particleCount }, () => ({
      angle: Math.random() * Math.PI * 2,
      r: innerRingR + Math.random() * (outerRingR - innerRingR),
      orbitSpeed: (Math.random() * 0.01 + 0.004) * (Math.random() > 0.5 ? 1 : -1),
      size: Math.random() * 1.6 + 0.6,
      alpha: Math.random() * 0.5 + 0.3,
      isCyan: Math.random() > 0.4,
    }))

    let ringAngle = 0
    let smoothEnergy = 0.1
    let animId: number

    const render = () => {
      const now = Date.now()
      const t = now * 0.0022

      // Energy based on state
      let targetEnergy = 0.1
      if (speaking || state === 'streaming') {
        targetEnergy = 0.55 + Math.sin(t * 5) * 0.3
      } else if (state === 'thinking' || state === 'tool_executing') {
        targetEnergy = 0.35 + Math.sin(t * 8) * 0.2
      } else if (listening) {
        targetEnergy = 0.42 + Math.sin(t * 6) * 0.22
      } else if (state === 'celebrating') {
        targetEnergy = 0.65 + Math.sin(t * 4) * 0.25
      } else {
        targetEnergy = 0.1 + Math.sin(t * 1.5) * 0.04
      }
      smoothEnergy += (targetEnergy - smoothEnergy) * 0.1

      const spinSpeed = (state === 'thinking' || state === 'tool_executing') ? 2.2 : (speaking || listening) ? 1.5 : 0.7
      ringAngle += 0.0015 * spinSpeed

      ctx.clearRect(0, 0, size, size)
      ctx.save()
      ctx.translate(cx, cy)

      // ── Layer 1: Ambient glow ──
      const ambientGrad = ctx.createRadialGradient(0, 0, coreR * 0.5, 0, 0, glowR * 1.1)
      ambientGrad.addColorStop(0, `rgba(0, 218, 248, ${0.18 + smoothEnergy * 0.2})`)
      ambientGrad.addColorStop(0.35, `rgba(94, 0, 255, ${0.14 + smoothEnergy * 0.14})`)
      ambientGrad.addColorStop(0.7, `rgba(0, 218, 248, ${0.06 + smoothEnergy * 0.06})`)
      ambientGrad.addColorStop(1, 'transparent')

      ctx.fillStyle = ambientGrad
      ctx.beginPath()
      ctx.arc(0, 0, glowR * 1.1, 0, Math.PI * 2)
      ctx.fill()

      ctx.globalCompositeOperation = 'lighter'

      // ── Layer 2: Outer tech ring ──
      ctx.save()
      ctx.rotate(ringAngle)

      // Outer ring border
      ctx.strokeStyle = `rgba(0, 218, 248, ${0.45 + smoothEnergy * 0.3})`
      ctx.lineWidth = Math.max(0.8, size * 0.007)
      ctx.beginPath()
      ctx.arc(0, 0, outerRingR, 0, Math.PI * 2)
      ctx.stroke()

      // Tick marks on outer ring
      if (!isSmall) {
        const ticks = 36
        for (let i = 0; i < ticks; i++) {
          const a = (i * Math.PI * 2) / ticks
          const isMajor = i % 4 === 0
          const tickLen = isMajor ? size * 0.016 : size * 0.008
          const cos = Math.cos(a)
          const sin = Math.sin(a)
          ctx.strokeStyle = isMajor
            ? `rgba(0, 218, 248, ${0.85 + smoothEnergy * 0.15})`
            : `rgba(0, 218, 248, ${0.35 + smoothEnergy * 0.2})`
          ctx.lineWidth = isMajor ? 1.2 : 0.6
          ctx.beginPath()
          ctx.moveTo(cos * outerRingR, sin * outerRingR)
          ctx.lineTo(cos * (outerRingR - tickLen), sin * (outerRingR - tickLen))
          ctx.stroke()
        }
      }
      ctx.restore()

      // ── Layer 3: Inner ring (counter-rotating) ──
      ctx.save()
      ctx.rotate(-ringAngle * 1.4)

      ctx.strokeStyle = `rgba(139, 92, 246, ${0.5 + smoothEnergy * 0.3})`
      ctx.lineWidth = Math.max(0.6, size * 0.005)
      ctx.beginPath()
      ctx.arc(0, 0, innerRingR, 0, Math.PI * 2)
      ctx.stroke()

      // Dashed arc segments
      if (!isSmall) {
        const segments = 8
        for (let i = 0; i < segments; i++) {
          const startA = (i * Math.PI * 2) / segments
          const endA = startA + (Math.PI * 2) / (segments * 1.8)
          ctx.strokeStyle = `rgba(167, 139, 250, ${0.65 + smoothEnergy * 0.25})`
          ctx.lineWidth = Math.max(1.2, size * 0.01)
          ctx.beginPath()
          ctx.arc(0, 0, innerRingR, startA, endA)
          ctx.stroke()
        }
      }
      ctx.restore()

      // ── Layer 4: Radial ray beams ──
      if (!isSmall) {
        const rays = speaking ? 16 : listening ? 12 : 8
        for (let i = 0; i < rays; i++) {
          const a = (i * Math.PI * 2) / rays + ringAngle * 0.5
          const rayLen = outerRingR * (0.7 + smoothEnergy * 0.4)
          const rayGrad = ctx.createLinearGradient(0, 0, Math.cos(a) * rayLen, Math.sin(a) * rayLen)
          rayGrad.addColorStop(0, `rgba(0, 218, 248, ${0.7 + smoothEnergy * 0.3})`)
          rayGrad.addColorStop(0.6, `rgba(94, 0, 255, ${0.2 + smoothEnergy * 0.2})`)
          rayGrad.addColorStop(1, 'transparent')

          ctx.strokeStyle = rayGrad
          ctx.lineWidth = Math.max(0.5, size * 0.006)
          ctx.beginPath()
          ctx.moveTo(Math.cos(a) * coreR, Math.sin(a) * coreR)
          ctx.lineTo(Math.cos(a) * rayLen, Math.sin(a) * rayLen)
          ctx.stroke()
        }
      }

      // ── Layer 5: Orbiting particles ──
      particles.forEach(p => {
        p.angle += p.orbitSpeed
        const px = Math.cos(p.angle) * p.r
        const py = Math.sin(p.angle) * p.r

        ctx.fillStyle = p.isCyan
          ? `rgba(0, 218, 248, ${p.alpha * (0.5 + smoothEnergy * 0.5)})`
          : `rgba(167, 139, 250, ${p.alpha * (0.5 + smoothEnergy * 0.4)})`
        ctx.beginPath()
        ctx.arc(px, py, p.size, 0, Math.PI * 2)
        ctx.fill()
      })

      // ── Layer 6: Core sphere ──
      const coreGrad = ctx.createRadialGradient(
        -coreR * 0.2, -coreR * 0.3, 0,
        0, 0, coreR * (1 + smoothEnergy * 0.15)
      )
      coreGrad.addColorStop(0, '#ffffff')
      coreGrad.addColorStop(0.3, `rgba(0, 218, 248, ${0.95 + smoothEnergy * 0.05})`)
      coreGrad.addColorStop(0.65, `rgba(0, 140, 210, ${0.8 + smoothEnergy * 0.15})`)
      coreGrad.addColorStop(0.88, `rgba(94, 0, 255, ${0.6 + smoothEnergy * 0.2})`)
      coreGrad.addColorStop(1, 'transparent')

      ctx.fillStyle = coreGrad
      ctx.beginPath()
      ctx.arc(0, 0, coreR * (1 + smoothEnergy * 0.15), 0, Math.PI * 2)
      ctx.fill()

      // Core specular highlight
      const specGrad = ctx.createRadialGradient(-coreR * 0.3, -coreR * 0.35, 0, -coreR * 0.1, -coreR * 0.1, coreR * 0.55)
      specGrad.addColorStop(0, 'rgba(255, 255, 255, 0.9)')
      specGrad.addColorStop(1, 'transparent')
      ctx.fillStyle = specGrad
      ctx.beginPath()
      ctx.arc(-coreR * 0.1, -coreR * 0.1, coreR * 0.55, 0, Math.PI * 2)
      ctx.fill()

      // ── Layer 7: Pulse wave when speaking starts ──
      const anim = answerAnimRef.current
      if (anim.active) {
        anim.progress += 0.03
        let pulseAlpha = 1
        let pulseScale = 1
        if (anim.progress < 0.4) {
          pulseScale = 0.8 + anim.progress * 0.6
          pulseAlpha = 1.0
        } else {
          const tp = (anim.progress - 0.4) / 0.6
          pulseScale = 1.04 + tp * 1.4
          pulseAlpha = Math.max(0, 1 - tp * 1.4)
        }
        if (anim.progress >= 1.0) anim.active = false

        ctx.save()
        ctx.scale(pulseScale, pulseScale)
        ctx.globalAlpha = pulseAlpha

        const waveGrad = ctx.createRadialGradient(0, 0, outerRingR * 0.6, 0, 0, outerRingR)
        waveGrad.addColorStop(0, 'transparent')
        waveGrad.addColorStop(0.85, 'rgba(0, 218, 248, 0.85)')
        waveGrad.addColorStop(1, 'transparent')
        ctx.fillStyle = waveGrad
        ctx.beginPath()
        ctx.arc(0, 0, outerRingR, 0, Math.PI * 2)
        ctx.fill()
        ctx.restore()
      }

      ctx.restore()
      animId = requestAnimationFrame(render)
    }

    animId = requestAnimationFrame(render)
    return () => cancelAnimationFrame(animId)
  }, [size, listening, speaking, state])

  const handleClick = () => {
    answerAnimRef.current = { active: true, progress: 0 }
    if (onClick) onClick()
  }

  return (
    <div
      className={`jarvis-orb-container ${interactive ? 'interactive' : ''} ${className}`}
      style={{
        width: size,
        height: size,
        display: 'inline-flex',
        alignItems: 'center',
        justifyContent: 'center',
        cursor: interactive ? 'pointer' : 'default',
        position: 'relative',
      }}
      onClick={interactive ? handleClick : undefined}
      role={interactive ? 'button' : undefined}
      tabIndex={interactive ? 0 : undefined}
      title={interactive ? 'Jarvis — Toque para interagir' : 'Jarvis Core'}
    >
      <canvas
        ref={canvasRef}
        style={{
          width: size,
          height: size,
          display: 'block',
          pointerEvents: 'none',
        }}
      />
    </div>
  )
}
