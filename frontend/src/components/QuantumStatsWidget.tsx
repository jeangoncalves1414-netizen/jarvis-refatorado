import { useEffect, useState } from 'react'

export function QuantumStatsWidget() {
  const [cpuUsage, setCpuUsage] = useState(18)
  const [ramUsage, setRamUsage] = useState(42)
  const [ping, setPing] = useState(14)
  const [activeThreads, setActiveThreads] = useState(8)

  useEffect(() => {
    const interval = setInterval(() => {
      setCpuUsage(Math.floor(12 + Math.random() * 25))
      setRamUsage(Math.floor(40 + Math.random() * 6))
      setPing(Math.floor(11 + Math.random() * 8))
      setActiveThreads(Math.floor(6 + Math.random() * 5))
    }, 2500)
    return () => clearInterval(interval)
  }, [])

  return (
    <div
      style={{
        background: 'rgba(10, 15, 26, 0.75)',
        backdropFilter: 'blur(12px)',
        border: '1px solid rgba(0, 218, 248, 0.25)',
        borderRadius: 12,
        padding: 16,
        color: '#fff',
        boxShadow: '0 8px 32px rgba(0, 218, 248, 0.1)',
        display: 'flex',
        flexDirection: 'column',
        gap: 12,
      }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <span style={{ fontSize: 11, color: '#fbbf24', fontWeight: 700, letterSpacing: 1 }}>
          ⚡ QUANTUM HUD · MONITOR DE SISTEMA
        </span>
        <span style={{ fontSize: 10, color: '#78e68c', background: 'rgba(120, 230, 140, 0.15)', padding: '2px 6px', borderRadius: 4 }}>
          ONLINE
        </span>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
        <div style={{ background: 'rgba(255,255,255,0.03)', padding: 10, borderRadius: 8, border: '1px solid rgba(255,255,255,0.05)' }}>
          <div style={{ fontSize: 11, color: '#aaa', marginBottom: 4 }}>CPU LOAD</div>
          <div style={{ fontSize: 18, fontWeight: 700, color: cpuUsage > 30 ? '#ffaa00' : '#fbbf24' }}>
            {cpuUsage}%
          </div>
          <div style={{ height: 4, background: 'rgba(255,255,255,0.1)', borderRadius: 2, marginTop: 6, overflow: 'hidden' }}>
            <div style={{ width: `${cpuUsage}%`, height: '100%', background: '#fbbf24', transition: 'width 0.5s ease' }} />
          </div>
        </div>

        <div style={{ background: 'rgba(255,255,255,0.03)', padding: 10, borderRadius: 8, border: '1px solid rgba(255,255,255,0.05)' }}>
          <div style={{ fontSize: 11, color: '#aaa', marginBottom: 4 }}>RAM UTILIZATION</div>
          <div style={{ fontSize: 18, fontWeight: 700, color: '#78e68c' }}>
            {ramUsage}%
          </div>
          <div style={{ height: 4, background: 'rgba(255,255,255,0.1)', borderRadius: 2, marginTop: 6, overflow: 'hidden' }}>
            <div style={{ width: `${ramUsage}%`, height: '100%', background: '#78e68c', transition: 'width 0.5s ease' }} />
          </div>
        </div>

        <div style={{ background: 'rgba(255,255,255,0.03)', padding: 10, borderRadius: 8, border: '1px solid rgba(255,255,255,0.05)' }}>
          <div style={{ fontSize: 11, color: '#aaa', marginBottom: 4 }}>NET LATENCY</div>
          <div style={{ fontSize: 16, fontWeight: 600, color: '#b8f4ff' }}>
            {ping} ms
          </div>
        </div>

        <div style={{ background: 'rgba(255,255,255,0.03)', padding: 10, borderRadius: 8, border: '1px solid rgba(255,255,255,0.05)' }}>
          <div style={{ fontSize: 11, color: '#aaa', marginBottom: 4 }}>ACTIVE THREADS</div>
          <div style={{ fontSize: 16, fontWeight: 600, color: '#b8f4ff' }}>
            {activeThreads} cores
          </div>
        </div>
      </div>
    </div>
  )
}
