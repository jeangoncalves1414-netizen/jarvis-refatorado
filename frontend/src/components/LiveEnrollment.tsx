import { useEffect, useRef, useState } from 'react'
import { asDataUrl, findReadWords, parseSelfEnrollment, parsePersonIntroduction, enrollmentModality, MIN_READING_COVERAGE } from './enrollmentReading'
import { openMicrophone } from '../utils/micPrefs'
import { followLocalReading, listenLocalAnswers } from './localReading'
import { EnrollmentCamera } from './EnrollmentCamera'
import { takeIdentityEvidence } from '../utils/identityEvidence'
import { speakGuidance } from '../utils/guidanceVoice'
import './appLock.css'

const introEvent = 'jarvis-live-introduction'
let inProgress = false
export function startIdentityEnrollment(detail: { name?: string; admin?: boolean; token?: string; offer?: boolean } = {}) {
  return !window.dispatchEvent(new CustomEvent(introEvent, { detail, cancelable: true }))
}
export function handleLiveIntroduction(text: string, identityToken?: string) {
  if (inProgress) {
    window.dispatchEvent(new CustomEvent('jarvis-enrollment-answer', { detail: text }))
    return true
  }
  const self = parseSelfEnrollment(text)
  if (self) return startIdentityEnrollment(self)
  const name = parsePersonIntroduction(text)
  if (!name) return false
  const event = new CustomEvent(introEvent, { detail: { name, offer: true, token: identityToken || takeIdentityEvidence() }, cancelable: true })
  return !window.dispatchEvent(event)
}

type Stage = 'name' | 'offer' | 'consent' | 'authorize' | 'reading' | 'faces' | 'done'
type Modality = 'voice' | 'face' | 'both'
async function api(payload: Record<string, unknown>) {
  const response = await fetch('/api/identity', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) })
  const data = await response.json()
  if (!response.ok || !data.ok) throw new Error(data.error || 'Não foi possível concluir esta etapa.')
  return data
}

export function LiveEnrollment() {
  const [name, setName] = useState('')
  const [admin, setAdmin] = useState(false)
  const [open, setOpen] = useState(false)
  const [stage, setStage] = useState<Stage>('consent')
  const [password, setPassword] = useState('')
  const [phrase, setPhrase] = useState('')
  const [sampleIndex, setSampleIndex] = useState(0)
  const [words, setWords] = useState<number[]>([])
  const [notice, setNotice] = useState('')
  const [busy, setBusy] = useState(false)
  const [saving, setSaving] = useState(false)
  const committing = useRef(false)
  const [recording, setRecording] = useState(false)
  const [micLevel, setMicLevel] = useState(0)
  const [images, setImages] = useState<string[]>([])
  const [voiceControls, setVoiceControls] = useState(true)
  const [listening, setListening] = useState(false)
  const [listenError, setListenError] = useState('')
  const [modality, setModality] = useState<Modality>('both')
  const [guidanceFinished, setGuidanceFinished] = useState('')
  const answerReader = useRef<(() => void) | null>(null)
  const ticket = useRef('')
  const token = useRef<string | undefined>(undefined)
  const rec = useRef<MediaRecorder | null>(null)
  const localReader = useRef<(() => void) | null>(null)
  const generation = useRef(0)
  const timer = useRef(0)
  const speaking = useRef(false)
  const guidance = useRef<AbortController | null>(null)
  const instruction = !open ? '' : stage === 'name' ? 'Olá! Eu sou o Jarvis. Como você se chama?'
    : stage === 'offer' ? `Prazer, ${name}! Quer que eu faça seu cadastro para reconhecer você nas próximas conversas?`
    : stage === 'consent' ? `${name}, quer que eu registre seu rosto, sua voz ou os dois? Ao escolher, você autoriza que eu use essas referências para reconhecer você.`
    : stage === 'authorize' ? 'Digite sua senha de desbloqueio do aplicativo no campo abaixo para continuar.'
    : stage === 'reading' ? (sampleIndex === 0 ? `${name}, vamos registrar três amostras da sua voz. Quando eu terminar, leia o texto na tela com sua voz normal.`
      : sampleIndex === 1 ? 'Agora leia a segunda frase como se estivesse conversando comigo.' : 'Para terminar, leia a última frase no seu ritmo normal.')
    : stage === 'faces' ? ''
    : `Tudo pronto, ${name}! Seu cadastro${admin ? ' de administrador' : ''} foi salvo.`
  useEffect(() => {
    setGuidanceFinished('')
    if (!instruction) return
    const controller = new AbortController(); guidance.current = controller
    speaking.current = true
    void speakGuidance(instruction, controller.signal).catch(error => {
      if (!controller.signal.aborted) setNotice(error instanceof Error ? error.message : 'A instrução está na tela.')
    }).finally(() => { if (!controller.signal.aborted) { speaking.current = false; setGuidanceFinished(instruction) } })
    return () => { controller.abort(); speaking.current = false }
  }, [instruction])

  function stop() {
    clearTimeout(timer.current)
    localReader.current?.(); localReader.current = null
    if (rec.current?.state === 'recording') rec.current.stop()
    rec.current?.stream.getTracks().forEach(track => track.stop())
  }
  function finish() {
    if (committing.current) return
    guidance.current?.abort()
    answerReader.current?.(); answerReader.current = null
    generation.current++; stop(); inProgress = false
    window.dispatchEvent(new CustomEvent('jarvis-enrollment-active', { detail: false }))
    if (ticket.current) void api({ action: 'enrollment_cancel', ticket: ticket.current }).catch(() => undefined)
    ticket.current = ''; token.current = undefined
    setOpen(false); setPassword(''); setImages([]); setBusy(false); setRecording(false)
  }
  useEffect(() => {
    const begin = (event: Event) => {
      if (inProgress) { event.preventDefault(); return }
      event.preventDefault(); inProgress = true; generation.current++
      window.dispatchEvent(new CustomEvent('jarvis-enrollment-active', { detail: true }))
      const detail = (event as CustomEvent<{ name?: string; token?: string; admin?: boolean; offer?: boolean }>).detail
      setAdmin(Boolean(detail.admin)); setName(detail.name || ''); token.current = detail.token
      setSampleIndex(0)
      setStage(detail.admin ? 'authorize' : !detail.name ? 'name' : detail.offer ? 'offer' : 'consent'); setPassword(''); setPhrase(''); setImages([]); setWords([]); setNotice(''); setVoiceControls(true); setModality('both'); setListenError(''); setOpen(true)
    }
    window.addEventListener(introEvent, begin)
    return () => { generation.current++; stop(); inProgress = false; window.dispatchEvent(new CustomEvent('jarvis-enrollment-active', { detail: false })); if (ticket.current) void api({ action: 'enrollment_cancel', ticket: ticket.current }).catch(() => undefined); window.removeEventListener(introEvent, begin) }
  }, [])

  async function authorize(chosen?: Modality) {
    const id = generation.current
    setBusy(true); setNotice('')
    const adminPassword = password; setPassword('')
    try {
      const identityToken = token.current; token.current = undefined
      const result = await api({ action: 'enrollment_authorize', name, identity_token: admin ? undefined : identityToken, admin_password: adminPassword, purpose: admin ? 'admin_reenroll' : 'user' })
      if (generation.current !== id) { void api({ action: 'enrollment_cancel', ticket: result.ticket }).catch(() => undefined); return }
      ticket.current = result.ticket; setPhrase(result.phrase)
      if (admin) setName(result.name)
      if (chosen) await prepare(chosen, id)
      else setStage('consent')
    } catch (error) {
      if (generation.current === id) {
        const message = error instanceof Error ? error.message : 'Não foi possível iniciar o cadastro.'
        const needsName = message === 'Informe seu nome para criar o primeiro administrador.'
        setStage(ticket.current ? 'consent' : admin && !needsName ? 'authorize' : 'name')
        setNotice(message)
      }
    }
    finally { if (generation.current === id) setBusy(false) }
  }
  async function prepare(chosen: Modality, id: number) {
    setNotice('Preparando reconhecimento local…')
    if (chosen !== 'voice') {
      const status = await api({ action: 'face_model_status' })
      if (generation.current !== id) return
      if (!status.ready) await api({ action: 'face_model_install' })
    }
    if (chosen !== 'face') {
      if (generation.current !== id) return
      const request = async (action: string) => {
        const response = await fetch('/api/voice/identity/model', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ action }) })
        const result = await response.json()
        if (!response.ok || !result.ok) throw new Error(result.error || 'Não foi possível preparar o reconhecimento de voz.')
        return result
      }
      const status = await request('status')
      if (generation.current !== id) return
      if (!status.ready) await request('install')
    }
    if (generation.current !== id) return
    setNotice(''); setStage(chosen === 'face' ? 'faces' : 'reading')
  }
  async function chooseModality(chosen: Modality) {
    setModality(chosen)
    if (!ticket.current) { await authorize(chosen); return }
    const id = generation.current
    setBusy(true)
    try { await prepare(chosen, id) }
    catch (error) { if (generation.current === id) setNotice(error instanceof Error ? error.message : 'Tente novamente.') }
    finally { if (generation.current === id) setBusy(false) }
  }
  async function save(faceImages: string[]) {
    if (committing.current) return
    committing.current = true; setSaving(true)
    const id = generation.current
    setBusy(true); setNotice('Salvando cadastro…'); setImages(faceImages)
    try {
      const result = await api({ action: 'live_enroll', ticket: ticket.current, consent: true, modality, face_consent: faceImages.length > 0, images: faceImages })
      if (generation.current !== id) return
      ticket.current = ''; setStage('done'); setNotice(result.warning || 'Referências registradas.')
      window.dispatchEvent(new CustomEvent('jarvis-identity-updated'))
      if (modality !== 'face') {
        try { localStorage.setItem('jarvis_speaker_identification', '1') } catch { /* optional storage */ }
        window.dispatchEvent(new CustomEvent('jarvis-speaker-preference', { detail: true }))
      }
    } catch (error) { if (generation.current === id) setNotice(error instanceof Error ? error.message : 'Falha no cadastro. Tente novamente.') }
    finally { committing.current = false; if (generation.current === id) { setBusy(false); setSaving(false) } }
  }
  async function record() {
    answerReader.current?.(); answerReader.current = null
    const id = generation.current
    setBusy(true); setNotice(''); setWords([])
    guidance.current?.abort(); speaking.current = false
    try {
      const stream = await openMicrophone({ echoCancellation: true, noiseSuppression: true, autoGainControl: true })
      if (generation.current !== id) { stream.getTracks().forEach(track => track.stop()); return }
      let recorder: MediaRecorder
      try { recorder = new MediaRecorder(stream) } catch (error) { stream.getTracks().forEach(track => track.stop()); throw error }
      rec.current = recorder
      const chunks: Blob[] = []
      recorder.ondataavailable = event => { if (event.data.size) chunks.push(event.data) }
      recorder.onstop = async () => {
        clearTimeout(timer.current); localReader.current?.(); localReader.current = null
        stream.getTracks().forEach(track => track.stop())
        if (generation.current !== id) return
        setRecording(false)
        try {
          const audio = await asDataUrl(new Blob(chunks, { type: recorder.mimeType }))
          if (generation.current !== id) return
          const result = await api({ action: 'enrollment_voice', ticket: ticket.current, consent: true, audio, content_type: recorder.mimeType, sample_index: sampleIndex })
          if (generation.current === id && result.next_phrase) {
            setWords([]); setPhrase(result.next_phrase); setSampleIndex(sampleIndex + 1)
            return
          }
          if (generation.current === id) { if (modality === 'both') setStage('faces'); else await save([]) }
        } catch (error) { if (generation.current === id) setNotice(error instanceof Error ? error.message : 'Repita a leitura.') }
        finally { if (generation.current === id) setBusy(false) }
      }
      const cleanup = await followLocalReading(stream, text => { if (generation.current === id && recorder.state === 'recording') { const read = findReadWords(phrase, text); setWords(read); if (read.length / phrase.split(/\s+/).length >= MIN_READING_COVERAGE) stop() } }, () => {
        if (generation.current === id) setNotice('Destaque temporariamente indisponível. A leitura será verificada ao concluir.')
      }, level => { if (generation.current === id) setMicLevel(level) })
      if (generation.current !== id) { cleanup(); stream.getTracks().forEach(track => track.stop()); return }
      localReader.current = cleanup
      recorder.start(); setRecording(true)
      timer.current = window.setTimeout(stop, 40000)
    } catch (error) { if (generation.current === id) { stop(); setBusy(false); setNotice(error instanceof Error ? error.message : 'Confira a permissão do microfone e tente novamente.') } }
  }
  useEffect(() => {
    if (open && stage === 'reading' && guidanceFinished === instruction) void record()
    if (open && stage === 'done' && guidanceFinished === instruction) finish()
  // One automatic action per completed instruction; retries remain explicit.
  }, [open, stage, guidanceFinished])
  const answer = useRef<(text: string) => void>(() => undefined)
  answer.current = text => {
    const normalized = text.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase().trim().replace(/[.!?,]/g, '')
    if (/^(?:jarvis )?(?:cancelar|cancela|cancelar cadastro|cancela cadastro)$/.test(normalized)) { finish(); return }
    if (recording && /^(?:jarvis )?(?:concluir leitura|terminar leitura|terminei)$/.test(normalized)) { stop(); return }
    if (speaking.current || busy) return
    if (!admin && (stage === 'name' || stage === 'consent') && (parseSelfEnrollment(text)?.admin || /^(?:como )?(?:admin|administradora?)$/.test(normalized))) {
      setAdmin(true); setStage('authorize'); return
    }
    if (stage === 'offer') {
      if (/\b(?:nao|agora nao|depois|cancelar)\b/.test(normalized)) { finish(); return }
      if (/\b(?:sim|pode|quero|vamos|claro|bora|autorizo)\b/.test(normalized)) setStage('consent')
      return
    }
    if (stage === 'name') {
      const spokenName = text.trim().replace(/^(?:jarvis[, ]+)?(?:meu nome [ée]|me chamo|(?:eu )?sou(?: (?:a|o))?)\s+/iu, '').replace(/[.!?]+$/, '').trim()
      if (spokenName.length >= 2 && spokenName.length <= 80) { setName(spokenName); setStage(admin ? 'authorize' : 'consent') }
      return
    }
    if (stage === 'consent') {
      if (/\b(?:nao|cancelar)\b/.test(normalized)) { finish(); return }
      const choice = enrollmentModality(normalized)
      if (choice) void chooseModality(choice)
    }
    else if (stage === 'reading' && /^(?:jarvis )?(?:sim|iniciar|iniciar leitura|comecar|comecar leitura)$/.test(normalized)) void record()
    else if (stage === 'done' && /^(?:concluir|terminar|pronto|obrigad[oa])$/.test(normalized)) finish()
  }
  useEffect(() => {
    const listener = (event: Event) => answer.current((event as CustomEvent<string>).detail)
    window.addEventListener('jarvis-enrollment-answer', listener)
    return () => window.removeEventListener('jarvis-enrollment-answer', listener)
  }, [])
  useEffect(() => {
    if (!open || !voiceControls || busy || recording || stage === 'faces' || stage === 'authorize') { setListening(false); return }
    let closed = false
    let stream: MediaStream | undefined
    let reader: (() => void) | undefined
    const cleanup = () => { if (closed) return; closed = true; reader?.(); stream?.getTracks().forEach(track => track.stop()) }
    answerReader.current = cleanup
    setListenError('')
    const failed = () => { if (!closed) { setListenError('Escuta indisponível. Confira o microfone e o leitor local; você também pode usar os campos e botões.'); setListening(false); setVoiceControls(false) } }
    void (async () => {
      try {
        stream = await openMicrophone({ echoCancellation: true, noiseSuppression: true, autoGainControl: true })
        if (closed) { stream.getTracks().forEach(track => track.stop()); return }
        reader = await listenLocalAnswers(stream, () => !closed && !speaking.current, text => answer.current(text), failed)
        if (closed) reader(); else setListening(true)
      } catch { failed(); cleanup() }
    })()
    return () => { cleanup(); if (answerReader.current === cleanup) answerReader.current = null }
  }, [open, stage, voiceControls, busy, recording])
  if (!open) return null
  return <div className="enrollment-overlay"><section className={`enrollment-dialog${stage === 'authorize' ? ' app-lock-card' : ''}`} role="dialog" aria-modal="true" aria-label={admin ? 'Refazer cadastro de administrador' : 'Apresentar uma pessoa'} onKeyDown={event => {
    if (event.key === 'Escape' && (!busy || recording)) { event.stopPropagation(); finish() }
    if (event.key !== 'Tab') return
    const elements = Array.from(event.currentTarget.querySelectorAll<HTMLElement>('button:not(:disabled), input:not(:disabled), select:not(:disabled)'))
    const target = event.shiftKey ? elements.at(-1) : elements[0]
    if ((event.shiftKey && document.activeElement === elements[0]) || (!event.shiftKey && document.activeElement === elements.at(-1))) { event.preventDefault(); target?.focus() }
  }}>
    <h2>{admin ? 'Refazer cadastro de administrador' : `Conhecer ${name}`}</h2><p aria-live="polite">{instruction}</p>
    {stage !== 'authorize' && stage !== 'faces' && <><button type="button" disabled={recording || busy} onClick={() => setVoiceControls(value => !value)}>{voiceControls ? 'Pausar respostas por voz' : 'Ativar respostas por voz'}</button><small>{listening ? 'Estou ouvindo. Responda depois da minha instrução.' : 'Os botões também estão disponíveis.'}</small></>}
    {listenError && <p role="alert">{listenError}</p>}
    {stage === 'name' && <p>Diga “me chamo…” seguido do seu nome.</p>}
    {!admin && (stage === 'name' || stage === 'consent') && <button disabled={busy} onClick={() => { setAdmin(true); setStage('authorize') }}>Continuar como administrador</button>}
    {stage === 'offer' && <><button onClick={() => setStage('consent')}>Sim, pode cadastrar</button><button onClick={finish}>Agora não</button></>}
    {admin && stage !== 'done' && <p>Ao concluir, as referências antigas de voz e rosto serão apagadas e substituídas. Seu nome, senha, memórias e permissões serão mantidos. Cancelar mantém o cadastro atual.</p>}
    {stage === 'consent' && <><p>Escolha por voz: “rosto”, “voz” ou “os dois”.</p><button disabled={busy} onClick={() => void chooseModality('face')}>Autorizar rosto</button><button disabled={busy} onClick={() => void chooseModality('voice')}>Autorizar voz</button><button disabled={busy} onClick={() => void chooseModality('both')}>Autorizar os dois</button><button onClick={finish}>Não cadastrar</button></>}
    {stage === 'authorize' && <form onSubmit={event => { event.preventDefault(); if (!busy && password) void authorize() }}><p>{name}</p><label>Senha administrativa — senha de desbloqueio do app <input autoFocus type="password" required maxLength={1024} autoComplete="current-password" value={password} disabled={busy} onChange={e => setPassword(e.target.value)} /></label><button type="submit" disabled={busy || !password}>{busy ? 'Verificando…' : 'Autorizar cadastro'}</button></form>}
    {stage === 'reading' && <><p className="enrollment-reading">{phrase.split(' ').map((word, i) => <span key={i} style={{ color: words.includes(i) ? '#36e6a5' : undefined }}>{word} </span>)}</p>{recording && <label>Microfone <meter aria-label="Volume do microfone" min={0} max={0.12} value={micLevel} /> {micLevel >= .006 ? 'Estou ouvindo.' : 'Aguardando sua voz…'}</label>}<button disabled={busy && !recording} onClick={recording ? stop : record}>{recording ? 'Concluir leitura' : busy ? 'Validando leitura…' : 'Iniciar leitura'}</button><small>{Math.floor(words.length / Math.max(1, phrase.split(/\s+/).length) * 100)}% reconhecido · mínimo 80%. Leia com sua voz normal; pode fazer pausas. A gravação termina automaticamente quando houver palavras suficientes, em até 40 segundos.</small></>}
    {stage === 'faces' && !busy && images.length === 0 && <EnrollmentCamera onComplete={photos => void save(photos)} />}
    {stage === 'faces' && !busy && images.length > 0 && <><button onClick={() => { setImages([]); setNotice('') }}>Refazer posições</button><button onClick={() => void save(images)}>Tentar salvar novamente</button></>}
    <p role="status">{notice}</p>
    <button disabled={saving} onClick={finish}>{saving ? 'Salvando cadastro…' : stage === 'done' ? 'Concluir' : 'Cancelar cadastro'}</button>
  </section></div>
}
