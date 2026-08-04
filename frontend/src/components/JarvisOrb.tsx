import { useEffect, useRef } from 'react'

type JarvisOrbProps = {
  size?: number
  listening?: boolean
  speaking?: boolean
  className?: string
}

export function JarvisOrb({ size = 112, listening = false, speaking = false, className = '' }: JarvisOrbProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const analyserRef = useRef<AnalyserNode | null>(null)
  const rafRef = useRef<number>(0)

  useEffect(() => {
    if (!listening) {
      if (rafRef.current) cancelAnimationFrame(rafRef.current)
      return
    }

    let stream: MediaStream | null = null
    let audioCtx: AudioContext | null = null

    const start = async () => {
      try {
        stream = await navigator.mediaDevices.getUserMedia({ audio: true })
        audioCtx = new AudioContext()
        const source = audioCtx.createMediaStreamSource(stream)
        const analyser = audioCtx.createAnalyser()
        analyser.fftSize = 256
        source.connect(analyser)
        analyserRef.current = analyser

        const canvas = canvasRef.current
        if (!canvas) return
        const ctx = canvas.getContext('2d')
        if (!ctx) return
        const data = new Uint8Array(analyser.frequencyBinCount)

        const draw = () => {
          analyser.getByteFrequencyData(data)
          const avg = data.reduce((a, b) => a + b, 0) / data.length
          const pulse = 1 + avg / 180
          const w = canvas.width
          const h = canvas.height
          ctx.clearRect(0, 0, w, h)
          const grad = ctx.createRadialGradient(w / 2, h / 2, 0, w / 2, h / 2, w / 2 * pulse)
          grad.addColorStop(0, '#b8f4ff')
          grad.addColorStop(0.4, '#00daf8')
          grad.addColorStop(0.7, '#9d05ff')
          grad.addColorStop(1, 'transparent')
          ctx.fillStyle = grad
          ctx.beginPath()
          ctx.arc(w / 2, h / 2, (w / 2 - 4) * pulse, 0, Math.PI * 2)
          ctx.fill()
          rafRef.current = requestAnimationFrame(draw)
        }
        draw()
      } catch {
        // fallback to CSS animation
      }
    }

    start()
    return () => {
      if (rafRef.current) cancelAnimationFrame(rafRef.current)
      stream?.getTracks().forEach(t => t.stop())
      audioCtx?.close()
      analyserRef.current = null
    }
  }, [listening])

  const stateClass = listening ? 'jarvis-orb-listening' : speaking ? 'jarvis-orb-speaking' : ''

  return (
    <div className={`jarvis-orb-wrap ${stateClass} ${className}`} style={{ width: size, height: size }}>
      <canvas ref={canvasRef} width={size} height={size} className="jarvis-orb-canvas" aria-hidden="true" />
      <div className="jarvis-orb-core">J</div>
      <div className="jarvis-orb-ring" aria-hidden="true" />
      <div className="jarvis-orb-ring jarvis-orb-ring-2" aria-hidden="true" />
    </div>
  )
}
