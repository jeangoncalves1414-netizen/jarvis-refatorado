// Listen to one answer at a time; silence separates answers so old words cannot
// approve a later consent step. The same local reader handles reference audio.
export async function listenLocalAnswers(stream: MediaStream, enabled: () => boolean, onText: (text: string) => void, onError: () => void) {
  const context = new AudioContext({ sampleRate: 16000 })
  const abort = new AbortController()
  try {
    const source = context.createMediaStreamSource(stream)
    const processor = context.createScriptProcessor(4096, 1, 1)
    let frames: Int16Array[] = [], count = 0, silence = 0, voiced = 0, pending = false
    let noiseFloor = 0.002
    const reset = () => { frames = []; count = 0; silence = 0; voiced = 0 }
    processor.onaudioprocess = event => {
      if (abort.signal.aborted || pending || !enabled()) { reset(); return }
      const samples = event.inputBuffer.getChannelData(0)
      const rms = Math.sqrt(samples.reduce((sum, value) => sum + value * value, 0) / samples.length)
      const threshold = Math.max(0.006, noiseFloor * 2.5)
      if (rms >= threshold) { voiced += samples.length; silence = 0 }
      else if (!count) { noiseFloor = .95 * noiseFloor + .05 * rms; return }
      else silence += samples.length
      frames.push(Int16Array.from(samples, v => Math.round(Math.max(-1, Math.min(1, v)) * 32767)))
      count += samples.length
      if (silence < 0.65 * 16000 && count < 10 * 16000) return
      if (voiced < 0.20 * 16000) { reset(); return }
      const body = new Blob(frames.map(frame => frame.buffer as ArrayBuffer))
      reset(); pending = true
      void fetch('/api/identity/reading', { method: 'POST', signal: abort.signal, headers: { 'Content-Type': 'application/octet-stream' }, body })
        .then(async response => {
          if (!response.ok) throw new Error('Escuta indisponível')
          const data = await response.json()
          if (!abort.signal.aborted && enabled() && data.text?.trim()) onText(data.text.trim())
        }).catch(() => { if (!abort.signal.aborted) onError() }).finally(() => { pending = false })
    }
    source.connect(processor); processor.connect(context.destination)
    const stop = () => { abort.abort(); processor.disconnect(); source.disconnect(); void context.close() }
    try { await context.resume() } catch (error) { stop(); throw error }
    return stop
  } catch (error) {
    if (context.state !== 'closed') void context.close()
    throw error
  }
}

// Reuse the recording stream and send short PCM prefixes to the local reader.
export async function followLocalReading(stream: MediaStream, onText: (text: string) => void, onError: () => void, onLevel?: (level: number) => void) {
  const context = new AudioContext({ sampleRate: 16000 })
  try {
    const source = context.createMediaStreamSource(stream)
    const processor = context.createScriptProcessor(4096, 1, 1)
    const frames: Int16Array[] = []
    const abort = new AbortController()
    let pending = false
    let count = 0
    let sent = 0
    processor.onaudioprocess = event => {
      if (count >= 44 * 16000) return
      const samples = event.inputBuffer.getChannelData(0)
      onLevel?.(Math.sqrt(samples.reduce((sum, v) => sum + v * v, 0) / samples.length))
      const frame = Int16Array.from(samples, v => Math.round(Math.max(-1, Math.min(1, v)) * 32767))
      frames.push(frame)
      count += frame.length
      if (pending || count - sent < 12000) return
      sent = count
      pending = true
      void fetch('/api/identity/reading', { method: 'POST', signal: abort.signal,
        headers: { 'Content-Type': 'application/octet-stream' }, body: new Blob(frames.map(f => f.buffer as ArrayBuffer)) })
        .then(async response => {
          if (!response.ok) throw new Error('Leitura indisponível')
          const data = await response.json()
          if (!abort.signal.aborted) onText(data.text || '')
        }).catch(() => { if (!abort.signal.aborted) onError() }).finally(() => { pending = false })
    }
    source.connect(processor)
    processor.connect(context.destination)
    function stop() {
      abort.abort()
      processor.disconnect()
      source.disconnect()
      void context.close()
    }
    try { await context.resume() } catch (error) { stop(); throw error }
    return stop
  } catch (error) {
    if (context.state !== 'closed') void context.close()
    throw error
  }
}
