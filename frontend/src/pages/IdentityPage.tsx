import { useEffect, useRef, useState } from 'react'

type Profile = { id: string; name?: string; role?: string; voice_samples?: number; face_samples?: number; created_at?: number }
type IdentityStatus = { profiles?: Profile[]; has_admin?: boolean }
type VoiceModelStatus = { ready?: boolean; model_downloaded?: boolean; model_size_bytes?: number; minimum_sample_seconds?: number; missing_dependencies?: string[] }
type CameraDevice = { deviceId: string; label: string }

const ENROLLMENT_PHRASES = [
  'Jarvis registra minha voz com clareza enquanto leio esta frase calma, natural e contínua para criar uma referência pessoal mais estável.',
  'Hoje eu falo em um ritmo confortável e com volume normal para criar uma referência segura da minha voz neste computador.',
  'A identificação local aprende características da minha fala enquanto eu leio esta frase inteira sem guardar a gravação original depois do processamento.',
  'Eu confirmo que autorizo o Jarvis a usar esta amostra para reconhecer minha voz durante conversas locais e nunca como senha de segurança.',
]

function chooseEnrollmentPhrase(previous = '') {
  const options = ENROLLMENT_PHRASES.filter(phrase => phrase !== previous)
  return options[Math.floor(Math.random() * options.length)] || ENROLLMENT_PHRASES[0]
}

function normalizeWord(value: string) {
  return value.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase().replace(/[^a-z0-9]/g, '')
}

function findReadWords(phrase: string, heard: string) {
  const expected = phrase.split(/\s+/).map(normalizeWord).filter(Boolean)
  const spoken = heard.split(/\s+/).map(normalizeWord).filter(Boolean)
  const matched: number[] = []
  let cursor = 0
  for (const word of spoken) {
    if (word === expected[cursor]) { matched.push(cursor); cursor += 1 }
    if (cursor >= expected.length) break
  }
  return matched
}

function asDataUrl(blob: Blob): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onerror = () => reject(new Error('Não foi possível ler a amostra.'))
    reader.onload = () => resolve(String(reader.result))
    reader.readAsDataURL(blob)
  })
}

export function IdentityPage() {
  const [status, setStatus] = useState<IdentityStatus>({ profiles: [] })
  const [name, setName] = useState('')
  const [password, setPassword] = useState('')
  const [adminPassword, setAdminPassword] = useState('')
  const [samplePassword, setSamplePassword] = useState('')
  const [profileId, setProfileId] = useState('')
  const [busy, setBusy] = useState('')
  const [notice, setNotice] = useState('')
  const [recording, setRecording] = useState(false)
  const [enrollmentPhrase, setEnrollmentPhrase] = useState(() => chooseEnrollmentPhrase())
  const [readWords, setReadWords] = useState<number[]>([])
  const [cameraOpen, setCameraOpen] = useState(false)
  const [cameraDevices, setCameraDevices] = useState<CameraDevice[]>([])
  const [selectedCameraId, setSelectedCameraId] = useState('')
  const [autoDetect, setAutoDetect] = useState(false)
  const [verification, setVerification] = useState<{ kind: string; matched?: boolean; confidence?: number; profile?: Profile | null; requires_confirmation?: boolean } | null>(null)
  const [voiceModel, setVoiceModel] = useState<VoiceModelStatus>({})
  const [identifyInCalls, setIdentifyInCalls] = useState(() => {
    try { return localStorage.getItem('jarvis_speaker_identification') === '1' } catch { return false }
  })
  const forgetActiveProfile = () => {
    try { localStorage.removeItem('jarvis-active-profile'); localStorage.removeItem('jarvis-active-profile-at') } catch { /* storage opcional */ }
    setNotice('Perfil ativo esquecido. O próximo chat não usará memória privada.')
  }
  const recorderRef = useRef<MediaRecorder | null>(null)
  const enrollmentRecognitionRef = useRef<any>(null)
  const chunksRef = useRef<Blob[]>([])
  const videoRef = useRef<HTMLVideoElement>(null)
  const streamRef = useRef<MediaStream | null>(null)

  const refresh = async () => {
    const response = await fetch('/api/identity')
    if (response.ok) setStatus(await response.json())
  }
  const refreshVoiceModel = async () => {
    const response = await fetch('/api/voice/identity/model', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ action: 'status' }) })
    if (response.ok) setVoiceModel(await response.json())
  }
  useEffect(() => { refresh().catch(() => undefined); refreshVoiceModel().catch(() => undefined) }, [])
  useEffect(() => () => {
    streamRef.current?.getTracks().forEach(track => track.stop())
    try { enrollmentRecognitionRef.current?.stop() } catch { /* optional feedback */ }
  }, [])
  const refreshCameraDevices = async () => {
    if (!navigator.mediaDevices?.enumerateDevices) return
    const devices = await navigator.mediaDevices.enumerateDevices()
    const cameras = devices.filter(device => device.kind === 'videoinput').map((device, index) => ({ deviceId: device.deviceId, label: device.label || `Câmera ${index + 1}` }))
    setCameraDevices(cameras)
    if (!selectedCameraId && cameras[0]) setSelectedCameraId(cameras[0].deviceId)
  }
  useEffect(() => { refreshCameraDevices().catch(() => undefined) }, [])
  useEffect(() => {
    if (cameraOpen && videoRef.current && streamRef.current) videoRef.current.srcObject = streamRef.current
  }, [cameraOpen])

  const call = async (payload: Record<string, unknown>) => {
    const response = await fetch('/api/identity', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) })
    const data = await response.json()
    if (!response.ok || !data.ok) throw new Error(data.error || 'Operação não concluída.')
    return data
  }
  const installVoiceModel = async () => {
    setBusy('voice-model'); setNotice('Baixando e preparando o modelo local de voz…')
    try {
      const response = await fetch('/api/voice/identity/model', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ action: 'install' }) })
      const data = await response.json()
      if (!response.ok || !data.ok) throw new Error(data.error || 'Não foi possível preparar o modelo.')
      setVoiceModel(data); setNotice('Modelo local pronto. Cadastre 2–3 amostras de 3–5 segundos por pessoa.')
    } catch (error) { setNotice(error instanceof Error ? error.message : 'Falha ao preparar o modelo de voz.') }
    finally { setBusy('') }
  }

  const enrollAdmin = async () => {
    setBusy('admin'); setNotice('')
    try {
      const data = await call({ action: 'enroll_admin', name, password })
      setProfileId(data.profile.id)
      setSamplePassword(password)
      setNotice('Administrador criado. Agora adicione uma amostra de voz e uma foto para habilitar as verificações.')
      await refresh()
    } catch (error) { setNotice(error instanceof Error ? error.message : 'Falha no cadastro.') }
    finally { setBusy('') }
  }
  const enrollProfile = async () => {
    setBusy('profile'); setNotice('')
    try { const data = await call({ action: 'enroll_profile', name, role: 'user', admin_password: adminPassword }); setProfileId(data.profile.id); setSamplePassword(adminPassword); setNotice('Perfil criado. Adicione as amostras com a senha administrativa.'); await refresh() }
    catch (error) { setNotice(error instanceof Error ? error.message : 'Falha ao criar perfil.') }
    finally { setBusy('') }
  }

  const addVoice = async (sample: string, contentType: string) => {
    if (!profileId || !samplePassword) { setNotice('Selecione um perfil e informe a senha dele antes de cadastrar a voz.'); return }
    setBusy('voice'); setNotice('Processando a amostra localmente…')
    try {
      await call({ action: 'add_sample', profile_id: profileId, password: samplePassword, kind: 'voice', sample, content_type: contentType })
      try { localStorage.setItem('jarvis_speaker_identification', '1') } catch { /* storage opcional */ }
      setIdentifyInCalls(true)
      setNotice('Amostra de voz adicionada. A identificação foi ativada nas próximas ligações.')
      await refresh()
    }
    catch (error) { setNotice(error instanceof Error ? error.message : 'Falha na amostra de voz.') }
    finally { setBusy('') }
  }

  const startVoice = async () => {
    if (!navigator.mediaDevices?.getUserMedia) { setNotice('O navegador não disponibiliza microfone neste ambiente.'); return }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      const recorder = new MediaRecorder(stream)
      chunksRef.current = []
      recorder.ondataavailable = event => { if (event.data.size) chunksRef.current.push(event.data) }
      recorder.onstop = async () => {
        try { enrollmentRecognitionRef.current?.stop() } catch { /* optional feedback */ }
        enrollmentRecognitionRef.current = null
        stream.getTracks().forEach(track => track.stop())
        const blob = new Blob(chunksRef.current, { type: recorder.mimeType || 'audio/webm' })
        await addVoice(await asDataUrl(blob), blob.type)
      }
      const browserWindow = window as Window & { SpeechRecognition?: any; webkitSpeechRecognition?: any }
      const Recognition = browserWindow.SpeechRecognition || browserWindow.webkitSpeechRecognition
      if (Recognition) {
        const recognition = new Recognition()
        recognition.lang = 'pt-BR'; recognition.continuous = true; recognition.interimResults = true
        recognition.onresult = (event: any) => {
          let heard = ''
          for (let index = 0; index < event.results.length; index += 1) heard += `${event.results[index][0]?.transcript || ''} `
          setReadWords(findReadWords(enrollmentPhrase, heard))
        }
        enrollmentRecognitionRef.current = recognition
        try { recognition.start() } catch { /* feedback remains optional */ }
      }
      recorderRef.current = recorder; recorder.start(); setRecording(true); setReadWords([]); setNotice('Leia a frase por inteiro, com voz natural. A gravação termina em até 12 segundos.')
      window.setTimeout(() => { if (recorder.state === 'recording') stopVoice() }, 12000)
    } catch { setNotice('Permissão de microfone negada ou indisponível.') }
  }
  const stopVoice = () => { if (recorderRef.current?.state === 'recording') { recorderRef.current.stop(); setRecording(false) } }

  const openCamera = async (cameraId = selectedCameraId) => {
    try {
      streamRef.current?.getTracks().forEach(track => track.stop())
      const video = cameraId ? { deviceId: { exact: cameraId } } : { facingMode: 'user' }
      const stream = await navigator.mediaDevices.getUserMedia({ video, audio: false })
      streamRef.current = stream
      setCameraOpen(true)
      await refreshCameraDevices()
    } catch { setNotice('Permissão de câmera negada ou indisponível.') }
  }
  const captureFace = async (verify = false) => {
    const video = videoRef.current
    if (!video || video.readyState < 2) { setNotice('A câmera ainda está iniciando.'); return }
    const canvas = document.createElement('canvas'); canvas.width = video.videoWidth; canvas.height = video.videoHeight; canvas.getContext('2d')?.drawImage(video, 0, 0)
    const sample = canvas.toDataURL('image/jpeg', 0.86)
    setBusy(verify ? 'verify-face' : 'face')
    try {
      const data = verify ? await call({ action: 'verify', kind: 'face', sample, content_type: 'image/jpeg' }) : await call({ action: 'add_sample', profile_id: profileId, password: samplePassword, kind: 'face', sample, content_type: 'image/jpeg' })
      if (verify) setVerification({ kind: 'face', ...data }); else { setNotice('Foto de referência adicionada.'); await refresh() }
    } catch (error) { setNotice(error instanceof Error ? error.message : 'Falha na imagem.') }
    finally { setBusy('') }
  }
  const verifyVoice = async () => {
    if (!navigator.mediaDevices?.getUserMedia) return
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true }); const recorder = new MediaRecorder(stream); const chunks: Blob[] = []
      recorder.ondataavailable = e => { if (e.data.size) chunks.push(e.data) }; recorder.onstop = async () => { stream.getTracks().forEach(t => t.stop()); const blob = new Blob(chunks, { type: recorder.mimeType || 'audio/webm' }); setBusy('verify-voice'); try { setVerification({ kind: 'voice', ...(await call({ action: 'verify', kind: 'voice', sample: await asDataUrl(blob), content_type: blob.type })) }) } catch (e) { setNotice(e instanceof Error ? e.message : 'Falha na verificação.') } finally { setBusy('') } }
      recorder.start(); setNotice('Fale agora por 3 segundos…'); window.setTimeout(() => { if (recorder.state === 'recording') recorder.stop() }, 3000)
    } catch { setNotice('Permissão de microfone negada.') }
  }

  useEffect(() => {
    if (!cameraOpen || !autoDetect) return
    const id = window.setInterval(() => { if (!busy) captureFace(true).catch(() => undefined) }, 5000)
    return () => window.clearInterval(id)
  }, [cameraOpen, autoDetect, busy])

  const selected = status.profiles?.find(profile => profile.id === profileId)
  return <section className="identity-page">
    <div className="identity-intro"><p className="eyebrow">SESSÃO DE TESTE · IDENTIDADE LOCAL</p><h2>Quem está falando com o Jarvis?</h2><p>Cadastre uma identidade com consentimento explícito. Voz e rosto ficam no computador e podem ser apagados pelo arquivo local de dados. Uma correspondência nunca ativa memórias privadas ou permissões sem confirmação manual.</p></div>
    <div className="identity-grid">
      <article className="identity-card"><span className="identity-step">{status.has_admin ? '01 · ACESSO ADMINISTRATIVO' : '01 · PRIMEIRO ADMINISTRADOR'}</span><h3>{status.has_admin ? 'Gerenciar pessoas' : 'Proteja o primeiro perfil'}</h3>{status.has_admin ? <><small>O administrador já existe. Use a senha abaixo somente para autorizar o cadastro de uma nova pessoa.</small><input value={name} onChange={e => setName(e.target.value)} placeholder="Nome da nova pessoa" /><input type="password" value={adminPassword} onChange={e => setAdminPassword(e.target.value)} placeholder="Senha do administrador" autoComplete="current-password" /><button disabled={!!busy || !name || !adminPassword} onClick={enrollProfile}>{busy === 'profile' ? 'Criando…' : 'Adicionar pessoa'}</button></> : <><input value={name} onChange={e => setName(e.target.value)} placeholder="Nome para chamar" /><input type="password" value={password} onChange={e => setPassword(e.target.value)} placeholder="Senha (mín. 8 caracteres)" autoComplete="new-password" /><button disabled={!!busy} onClick={enrollAdmin}>{busy === 'admin' ? 'Criando…' : 'Criar administrador'}</button></>}</article>
      <article className="identity-card"><span className="identity-step">02 · VOZ LOCAL</span><h3>Modelo de identificação</h3><p>{voiceModel.ready ? `Pronto no computador (${Math.round((voiceModel.model_size_bytes || 0) / 1024 / 1024)} MB).` : 'Ainda não preparado. O download é único e o reconhecimento funciona localmente.'}</p>{!voiceModel.ready && <button disabled={!!busy} onClick={installVoiceModel}>{busy === 'voice-model' ? 'Preparando…' : 'Preparar modelo de voz'}</button>}{voiceModel.ready && <label className="identity-auto"><input type="checkbox" checked={identifyInCalls} onChange={e => { setIdentifyInCalls(e.target.checked); localStorage.setItem('jarvis_speaker_identification', e.target.checked ? '1' : '0') }} /> identificar a voz de cada turno nas ligações</label>}<small>Use 2–3 amostras de 3–5 segundos, uma pessoa por vez. Não reconhece vozes sobrepostas nesta primeira versão.</small></article>
      <article className="identity-card"><span className="identity-step">03 · PERFIL</span><h3>Amostras de referência</h3><select value={profileId} onChange={e => { setProfileId(e.target.value); setSamplePassword('') }}><option value="">Selecione um perfil</option>{status.profiles?.map(profile => <option key={profile.id} value={profile.id}>{profile.name} · {profile.role}</option>)}</select><input type="password" value={samplePassword} onChange={e => setSamplePassword(e.target.value)} placeholder="Senha do perfil selecionado" autoComplete="current-password" /><div className="identity-enrollment-phrase"><small>Leia naturalmente a frase abaixo. Palavras verdes foram percebidas como feedback e a transcrição não é salva.</small><p>{enrollmentPhrase.split(/\s+/).map((word, index) => <span key={`${word}-${index}`} style={{ color: readWords.includes(index) ? '#36e6a5' : undefined, transition: 'color 160ms ease' }}>{word} </span>)}</p><button type="button" disabled={recording} onClick={() => { setEnrollmentPhrase(chooseEnrollmentPhrase(enrollmentPhrase)); setReadWords([]) }}>↻ Trocar frase</button></div><select value={selectedCameraId} onChange={e => { setSelectedCameraId(e.target.value); if (cameraOpen) openCamera(e.target.value).catch(() => undefined) }} aria-label="Escolha a câmera"><option value="">Câmera padrão</option>{cameraDevices.map((camera, index) => <option key={camera.deviceId || index} value={camera.deviceId}>{camera.label}</option>)}</select><div className="identity-actions"><button disabled={!voiceModel.ready || !profileId || !samplePassword || !!busy || recording} onClick={startVoice}>{recording ? 'Gravando…' : 'Gravar leitura'}</button>{recording && <button type="button" onClick={stopVoice}>Encerrar leitura</button>}<button disabled={!profileId || !samplePassword || !!busy} onClick={() => openCamera()}>Abrir câmera escolhida</button><button disabled={!!busy} onClick={() => refreshCameraDevices().catch(() => setNotice('Não foi possível listar as câmeras.'))}>Atualizar lista</button></div>{selected && <p className="identity-meta">{selected.voice_samples || 0} voz · {selected.face_samples || 0} rosto</p>}</article>
    </div>
    {cameraOpen && <div className="identity-camera"><video ref={videoRef} autoPlay muted playsInline /><label className="identity-auto"><input type="checkbox" checked={autoDetect} onChange={e => setAutoDetect(e.target.checked)} /> detectar perfis conhecidos automaticamente a cada 5 s</label><div><button onClick={() => captureFace(false)} disabled={!!busy || !profileId || !samplePassword}>Salvar foto</button><button onClick={() => captureFace(true)} disabled={!!busy}>Verificar rosto</button><button onClick={() => { streamRef.current?.getTracks().forEach(t => t.stop()); setCameraOpen(false); setAutoDetect(false) }}>Fechar</button></div></div>}
    <article className="identity-card identity-verify"><span className="identity-step">04 · TESTE</span><h3>Verificar sem conceder acesso automaticamente</h3><p>70% indica voz provável; 80% indica correspondência forte. Nenhuma faixa altera permissões ou memórias privadas.</p><div className="identity-actions"><button disabled={!voiceModel.ready || !!busy} onClick={verifyVoice}>Testar voz</button><button disabled={!!busy || !cameraOpen} onClick={() => captureFace(true)}>Testar rosto atual</button><button type="button" onClick={forgetActiveProfile}>Esquecer perfil ativo</button></div>{verification && <div className={`identity-result ${verification.matched ? 'matched' : 'unknown'}`}><strong>{verification.matched ? `${verification.requires_confirmation ? 'Voz provável' : 'Correspondência forte'}: ${verification.profile?.name}` : 'Pessoa não confirmada'}</strong><span>Confiança: {Math.round((verification.confidence || 0) * 100)}%</span></div>}</article>
    {notice && <p className="identity-notice">{notice}</p>}
  </section>
}
