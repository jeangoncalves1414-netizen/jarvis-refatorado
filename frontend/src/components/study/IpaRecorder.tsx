import { openMicrophone } from '../../utils/micPrefs'
import { useEffect, useRef, useState } from 'react'

// Gemini accepts PCM WAV independently of the browser's recorder container.
async function wav(blob: Blob) {
  const context = new AudioContext({sampleRate: 16000})
  try {
    const buffer = await context.decodeAudioData(await blob.arrayBuffer())
    const samples = buffer.getChannelData(0)
    const bytes = new ArrayBuffer(44 + samples.length * 2)
    const view = new DataView(bytes)
    const tag = (offset:number, text:string) => [...text].forEach((letter,i) => view.setUint8(offset+i,letter.charCodeAt(0)))
    tag(0,'RIFF'); view.setUint32(4,bytes.byteLength-8,true); tag(8,'WAVE'); tag(12,'fmt ')
    view.setUint32(16,16,true); view.setUint16(20,1,true); view.setUint16(22,1,true)
    view.setUint32(24,buffer.sampleRate,true); view.setUint32(28,buffer.sampleRate*2,true)
    view.setUint16(32,2,true); view.setUint16(34,16,true); tag(36,'data'); view.setUint32(40,bytes.byteLength-44,true)
    samples.forEach((sample,i) => view.setInt16(44+i*2,Math.round(Math.max(-1,Math.min(1,sample))*32767),true))
    return bytes
  } finally { await context.close() }
}

export function IpaRecorder() {
  const recorder = useRef<MediaRecorder|null>(null)
  const lifetime = useRef<AbortController|null>(null)
  const timer = useRef(0)
  const [mode,setMode] = useState<'idle'|'waiting'|'recording'>('idle')
  const [message,setMessage] = useState('')
  useEffect(() => {
    lifetime.current = new AbortController()
    return () => {
      lifetime.current?.abort()
      window.clearTimeout(timer.current)
      const rec = recorder.current
      if (rec) {rec.onstop = null; if (rec.state === 'recording') rec.stop(); rec.stream.getTracks().forEach(t => t.stop())}
    }
  }, [])
  async function record() {
    const signal = lifetime.current?.signal
    setMode('waiting'); setMessage('')
    let stream:MediaStream|undefined
    try {
      stream = await openMicrophone()
      if (signal?.aborted) {stream.getTracks().forEach(t => t.stop()); return}
      const rec = new MediaRecorder(stream)
      recorder.current = rec
      const chunks:Blob[] = []
      rec.ondataavailable = e => chunks.push(e.data)
      rec.onstop = async () => {
        window.clearTimeout(timer.current)
        rec.stream.getTracks().forEach(t => t.stop())
        recorder.current = null
        setMode('waiting'); setMessage('Transcrevendo…')
        try {
          const body = await wav(new Blob(chunks,{type:rec.mimeType}))
          const response = await fetch('/api/language/ipa',{method:'POST',headers:{'Content-Type':'audio/wav'},body,signal})
          const data = await response.json()
          if (!response.ok) throw new Error(data.error || 'Falha ao transcrever.')
          setMessage(data.ipa)
        } catch (err) {if (!signal?.aborted) setMessage(err instanceof Error ? err.message : 'Falha na transcrição.')}
        finally {if (!signal?.aborted) setMode('idle')}
      }
      rec.start()
      setMode('recording')
      timer.current = window.setTimeout(() => {if (rec.state === 'recording') rec.stop()},15000)
    } catch {stream?.getTracks().forEach(t => t.stop()); if (!signal?.aborted) {setMode('idle');setMessage('Microfone indisponível. Verifique a permissão do navegador.')}}
  }
  return <details><summary>Transcrição fonética (IPA)</summary>
    <p>Grave até 15 segundos. Ao terminar, o áudio será enviado ao Gemini para estimar os sons pronunciados.</p>
    <button disabled={mode==='waiting'} onClick={() => mode==='recording' ? recorder.current?.stop() : record()}>{mode==='recording' ? 'Terminar e transcrever' : 'Gravar para IPA'}</button>
    <output aria-live="polite">{message}</output>
  </details>
}
