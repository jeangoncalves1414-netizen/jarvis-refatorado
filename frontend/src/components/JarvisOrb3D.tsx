import React, { useEffect, useRef } from 'react'

export type AgentState = 'idle' | 'thinking' | 'streaming' | 'tool_executing' | 'celebrating'

export interface JarvisOrb3DProps {
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

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    if (!ctx) return

    const dpr = window.devicePixelRatio || 1
    canvas.width = size * dpr
    canvas.height = size * dpr
    ctx.scale(dpr, dpr)

    let animId: number
    let timeoutId: number
    let time = 0
    let rotAngle = 0
    let counterRotAngle = 0
    let pulseProgress = 0

    const particleCount = size < 80 ? 8 : size < 140 ? 16 : 42
    const particles = Array.from({ length: particleCount }, () => {
      const radius = (Math.random() * 0.38 + 0.12) * size
      const angle = Math.random() * Math.PI * 2
      return {
        x: Math.cos(angle) * radius,
        y: Math.sin(angle) * radius,
        radius,
        angle,
        speed: (Math.random() * 0.015 + 0.008) * (Math.random() > 0.5 ? 1 : -1),
        size: Math.random() * 2.2 + 1,
        opacity: Math.random() * 0.7 + 0.3,
      }
    })

    const getPalette = () => {
      if (state === 'thinking' || state === 'tool_executing') {
        return {
          primary: '#a855f7',
          secondary: '#c084fc',
          accent: '#e9d5ff',
          core: '#ffffff',
          outerGlow: 'rgba(168, 85, 247, 0.45)',
          innerGlow: 'rgba(192, 132, 252, 0.25)',
          rotSpeed: 0.035,
          pulseSpeed: 4.5,
        }
      }
      if (state === 'celebrating') {
        return {
          primary: '#22c55e',
          secondary: '#4ade80',
          accent: '#bbf7d0',
          core: '#ffffff',
          outerGlow: 'rgba(34, 197, 94, 0.45)',
          innerGlow: 'rgba(74, 222, 128, 0.25)',
          rotSpeed: 0.02,
          pulseSpeed: 3,
        }
      }
      if (listening) {
        return {
          primary: '#ec4899',
          secondary: '#f472b6',
          accent: '#00daf8',
          core: '#ffffff',
          outerGlow: 'rgba(236, 72, 153, 0.48)',
          innerGlow: 'rgba(0, 218, 248, 0.3)',
          rotSpeed: 0.025,
          pulseSpeed: 3.8,
        }
      }
      if (speaking) {
        return {
          primary: '#10b981',
          secondary: '#34d399',
          accent: '#6ee7b7',
          core: '#ffffff',
          outerGlow: 'rgba(16, 185, 129, 0.48)',
          innerGlow: 'rgba(52, 211, 153, 0.28)',
          rotSpeed: 0.028,
          pulseSpeed: 5,
        }
      }
      return {
        primary: '#00daf8',
        secondary: '#38bdf8',
        accent: '#b8f4ff',
        core: '#ffffff',
        outerGlow: 'rgba(0, 218, 248, 0.38)',
        innerGlow: 'rgba(0, 218, 248, 0.15)',
        rotSpeed: 0.012,
        pulseSpeed: 1.8,
      }
    }

    const render = () => {
      const cx = size / 2
      const cy = size / 2
      const pScale = size / 160
      const palette = getPalette()

      time += 0.016
      rotAngle += palette.rotSpeed
      counterRotAngle -= palette.rotSpeed * 1.35
      pulseProgress = (Math.sin(time * palette.pulseSpeed) + 1) * 0.5

      ctx.clearRect(0, 0, size, size)

      // Ambient radial glow
      const glowR = 64 * pScale
      const ambientGrad = ctx.createRadialGradient(cx, cy, 0, cx, cy, glowR * 1.25)
      ambientGrad.addColorStop(0, palette.outerGlow)
      ambientGrad.addColorStop(0.5, palette.innerGlow)
      ambientGrad.addColorStop(1, 'rgba(0, 0, 0, 0)')
      ctx.beginPath()
      ctx.arc(cx, cy, glowR * 1.25, 0, Math.PI * 2)
      ctx.fillStyle = ambientGrad
      ctx.fill()

      // Outer tech ring (with ticks and arcs)
      const outerR = 68 * pScale
      ctx.save()
      ctx.translate(cx, cy)
      ctx.rotate(rotAngle)

      ctx.beginPath()
      ctx.arc(0, 0, outerR, 0, Math.PI * 2)
      ctx.strokeStyle = `rgba(0, 218, 248, ${0.25 + pulseProgress * 0.15})`
      ctx.lineWidth = Math.max(1, 1.2 * pScale)
      ctx.stroke()

      // 24 Tachometer tick marks
      const tickCount = 24
      for (let i = 0; i < tickCount; i++) {
        const angle = (i * Math.PI * 2) / tickCount
        const isMajor = i % 6 === 0
        const tickLen = (isMajor ? 6 : 3) * pScale
        ctx.beginPath()
        ctx.moveTo(Math.cos(angle) * (outerR - tickLen), Math.sin(angle) * (outerR - tickLen))
        ctx.lineTo(Math.cos(angle) * outerR, Math.sin(angle) * outerR)
        ctx.strokeStyle = isMajor ? palette.primary : 'rgba(255, 255, 255, 0.35)'
        ctx.lineWidth = Math.max(1, (isMajor ? 1.8 : 1) * pScale)
        ctx.stroke()
      }

      // 3 Outer accent arcs
      for (let i = 0; i < 3; i++) {
        const startA = i * ((Math.PI * 2) / 3) + 0.2
        const endA = startA + 0.7
        ctx.beginPath()
        ctx.arc(0, 0, outerR + 3 * pScale, startA, endA)
        ctx.strokeStyle = palette.primary
        ctx.lineWidth = Math.max(1, 2.2 * pScale)
        ctx.stroke()
      }
      ctx.restore()

      // Inner counter-rotating ring
      const innerR = 52 * pScale
      ctx.save()
      ctx.translate(cx, cy)
      ctx.rotate(counterRotAngle)

      const segmentCount = 16
      for (let i = 0; i < segmentCount; i++) {
        const segAngle = (i * Math.PI * 2) / segmentCount
        ctx.beginPath()
        ctx.arc(0, 0, innerR, segAngle, segAngle + 0.24)
        ctx.strokeStyle = i % 2 === 0 ? palette.secondary : palette.primary
        ctx.lineWidth = Math.max(1, 3.2 * pScale)
        ctx.stroke()

        if (i % 4 === 0) {
          ctx.beginPath()
          ctx.moveTo(Math.cos(segAngle + 0.12) * (innerR - 6 * pScale), Math.sin(segAngle + 0.12) * (innerR - 6 * pScale))
          ctx.lineTo(Math.cos(segAngle + 0.12) * (innerR - 14 * pScale), Math.sin(segAngle + 0.12) * (innerR - 14 * pScale))
          ctx.strokeStyle = `rgba(255, 255, 255, ${0.4 + pulseProgress * 0.3})`
          ctx.lineWidth = Math.max(1, 1.4 * pScale)
          ctx.stroke()
        }
      }
      ctx.restore()

      // Audio-reactive sine wave ring
      const waveR = (38 + pulseProgress * 4) * pScale
      ctx.beginPath()
      const wavePoints = 36
      for (let i = 0; i <= wavePoints; i++) {
        const angle = (i * Math.PI * 2) / wavePoints
        const waveDisp = (listening || speaking)
          ? Math.sin(angle * 8 + time * 8) * 3.5 * pScale
          : Math.sin(angle * 4 + time * 3) * 1.5 * pScale
        const r = waveR + waveDisp
        const px = cx + Math.cos(angle) * r
        const py = cy + Math.sin(angle) * r
        if (i === 0) ctx.moveTo(px, py)
        else ctx.lineTo(px, py)
      }
      ctx.closePath()
      ctx.strokeStyle = `rgba(${speaking ? '16, 185, 129' : listening ? '236, 72, 153' : '0, 218, 248'}, ${0.6 + pulseProgress * 0.3})`
      ctx.lineWidth = Math.max(1, 1.6 * pScale)
      ctx.stroke()

      // Orbiting particles
      for (const p of particles) {
        p.angle += p.speed * (state === 'thinking' ? 2.2 : 1)
        p.x = cx + Math.cos(p.angle) * p.radius * (1 + pulseProgress * 0.08)
        p.y = cy + Math.sin(p.angle) * p.radius * (1 + pulseProgress * 0.08)
        ctx.beginPath()
        ctx.arc(p.x, p.y, p.size * pScale, 0, Math.PI * 2)
        ctx.fillStyle = `rgba(${
          palette.primary === '#a855f7'
            ? '192, 132, 252'
            : palette.primary === '#10b981'
            ? '110, 231, 183'
            : '184, 244, 255'
        }, ${p.opacity * (0.5 + pulseProgress * 0.5)})`
        ctx.fill()
      }

      // Glowing core aura
      const coreR = (18 + pulseProgress * 3) * pScale
      const auraGrad = ctx.createRadialGradient(cx, cy, 0, cx, cy, coreR * 1.8)
      auraGrad.addColorStop(0, palette.accent)
      auraGrad.addColorStop(0.35, palette.primary)
      auraGrad.addColorStop(0.7, palette.outerGlow)
      auraGrad.addColorStop(1, 'rgba(0, 0, 0, 0)')
      ctx.beginPath()
      ctx.arc(cx, cy, coreR * 1.8, 0, Math.PI * 2)
      ctx.fillStyle = auraGrad
      ctx.fill()

      // Core sphere
      const coreGrad = ctx.createRadialGradient(cx, cy, 0, cx, cy, coreR)
      coreGrad.addColorStop(0, '#ffffff')
      coreGrad.addColorStop(0.4, palette.accent)
      coreGrad.addColorStop(0.85, palette.primary)
      coreGrad.addColorStop(1, 'rgba(255, 255, 255, 0.4)')
      ctx.beginPath()
      ctx.arc(cx, cy, coreR, 0, Math.PI * 2)
      ctx.fillStyle = coreGrad
      ctx.fill()

      // Micro core ring and dot
      const microR = 6 * pScale
      ctx.beginPath()
      ctx.arc(cx, cy, microR, 0, Math.PI * 2)
      ctx.strokeStyle = '#ffffff'
      ctx.lineWidth = Math.max(1, 1.5 * pScale)
      ctx.stroke()

      ctx.beginPath()
      ctx.arc(cx, cy, 2 * pScale, 0, Math.PI * 2)
      ctx.fillStyle = '#ffffff'
      ctx.shadowColor = palette.primary
      ctx.shadowBlur = 10 * pScale
      ctx.fill()
      ctx.shadowBlur = 0

      // Core crosshairs
      const crossArm = 4 * pScale
      const crossDist = 8 * pScale
      const crosshairs = [[0, -1], [1, 0], [0, 1], [-1, 0]]
      for (const [dx, dy] of crosshairs) {
        ctx.beginPath()
        ctx.moveTo(cx + dx * crossDist, cy + dy * crossDist)
        ctx.lineTo(cx + dx * (crossDist + crossArm), cy + dy * (crossDist + crossArm))
        ctx.strokeStyle = 'rgba(255, 255, 255, 0.7)'
        ctx.lineWidth = Math.max(1, 1.2 * pScale)
        ctx.stroke()
      }

      // Tactical text label below orb
      if (size >= 160) {
        ctx.fillStyle = 'rgba(255, 255, 255, 0.45)'
        ctx.font = `600 ${Math.round(8 * pScale)}px "DM Mono", monospace`
        ctx.textAlign = 'center'
        ctx.textBaseline = 'top'
        const label = (state === 'thinking' || state === 'tool_executing')
          ? 'NEURAL CORE'
          : listening
          ? 'AUDIO INPUT'
          : speaking
          ? 'VOICE SYNTH'
          : 'QUANTUM ARC'
        ctx.fillText(label, cx, cy + outerR + 8 * pScale)
      }

      if (document.hidden) {
        timeoutId = window.setTimeout(() => {
          animId = requestAnimationFrame(render)
        }, 400)
        return
      }

      animId = requestAnimationFrame(render)
    }

    render()

    return () => {
      cancelAnimationFrame(animId)
      window.clearTimeout(timeoutId)
    }
  }, [size, listening, speaking, state])

  return (
    <canvas
      ref={canvasRef}
      style={{
        width: size,
        height: size,
        display: 'block',
        cursor: interactive ? 'pointer' : 'default',
        userSelect: 'none',
      }}
      className={`jarvis-orb-canvas ${className}`}
      onClick={onClick}
      title={`Jarvis Quantum Core (${state})`}
    />
  )
}
