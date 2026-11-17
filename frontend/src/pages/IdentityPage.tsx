import { rememberIdentityEvidence } from '../utils/identityEvidence'
import { openMicrophone } from '../utils/micPrefs'
import { cameraLabel, openConfiguredCamera, registerDetectedCameras } from '../utils/cameraCatalog'
import { chooseEnrollmentPhrase, findReadWords, asDataUrl } from '../components/enrollmentReading'
import { followLocalReading } from '../components/localReading'
import { startIdentityEnrollment } from '../components/LiveEnrollment'
import { useEffect, useRef, useState } from 'react'

type Profile = { id: string; name?: string; role?: string; voice_samples?: number; face_samples?: number; created_at?: number; permissions?: string[]; command_level?: string }
type IdentityStatus = { profiles?: Profile[]; has_admin?: boolean }
type VoiceModelStatus = { ready?: boolean; model_downloaded?: boolean; model_size_bytes?: number; minimum_sample_seconds?: number; missing_dependencies?: string[] }
type CameraDevice = { deviceId: string; label: string }

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
    faceRequest.current++
    rememberIdentityEvidence()
    try { localStorage.removeItem('jarvis-active-profile'); localStorage.removeItem('jarvis-active-profile-at') } catch { /* storage opcional */ }
    setNotice('Perfil ativo esquecido. O próximo chat não usará memória privada.')
  }
  const recorderRef = useRef<MediaRecorder | null>(null)
  const localReader = useRef<(() => void) | null>(null)
  const audioRequest = useRef(0)
  const audioPending = useRef(false)
  const audioTimer = useRef<number | undefined>(undefined)
  const videoRef = useRef<HTMLVideoElement>(null)
  const streamRef = useRef<MediaStream | null>(null)
  const cameraRequest = useRef(0)
  const faceRequest = useRef(0)

  const refresh = async () => {
    const response = await fetch('/api/identity')
    if (response.ok) setStatus(await response.json())
  }
  const refreshVoiceModel = async () => {
    const response = await fetch('/api/voice/identity/model', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ action: 'status' }) })
    if (response.ok) setVoiceModel(await response.json())
  }
  useEffect(() => { refresh().catch(() => undefined); refreshVoiceModel().catch(() => undefined) }, [])
  useEffect(() => {
    const updated = () => { void refresh().catch(() => undefined) }
    window.addEventListener('jarvis-identity-updated', updated)
    return () => window.removeEventListener('jarvis-identity-updated', updated)
  }, [])
  useEffect(() => () => {
    cameraRequest.current++
    faceRequest.current++
    audioRequest.current++
    window.clearTimeout(audioTimer.current)
    const recorder = recorderRef.current
    if (recorder) {
      recorder.onstop = null
      if (recorder.state !== 'inactive') recorder.stop()
      recorder.stream.getTracks().forEach(track => track.stop())
    }
    streamRef.current?.getTracks().forEach(track => track.stop())
    localReader.current?.(); localReader.current = null
  }, [])
  const refreshCameraDevices = async () => {
    if (!navigator.mediaDevices?.enumerateDevices) return
    const devices = await navigator.mediaDevices.enumerateDevices()
    const cameras = registerDetectedCameras(devices).filter(c => c.enabled && devices.some(d => d.kind === 'videoinput' && d.deviceId === c.id)).map(c => ({ deviceId: c.id, label: cameraLabel(c) }))
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
    if (!profileId || !samplePassword) { setNotice('Selecione um perfil e informe a senha de desbloqueio antes de cadastrar a voz.'); return }
    setBusy('voice'); setNotice('Processando a amostra localmente…')
    try {
      await call({ action: 'add_sample', profile_id: profileId, password: samplePassword, kind: 'voice', sample, content_type: contentType })
      try { localStorage.setItem('jarvis_speaker_identification', '1') } catch { /* storage opcional */ }
      setIdentifyInCalls(true)
      window.dispatchEvent(new CustomEvent('jarvis-speaker-preference', { detail: true }))
      setNotice('Amostra de voz adicionada. A identificação foi ativada nas próximas ligações.')
      await refresh()
    }
    catch (error) { setNotice(error instanceof Error ? error.message : 'Falha na amostra de voz.') }
    finally { setBusy('') }
  }

  const startVoice = async () => {
    if (audioPending.current) return
    if (!navigator.mediaDevices?.getUserMedia) { setNotice('O navegador não disponibiliza microfone neste ambiente.'); return }
    audioPending.current = true
    const request = ++audioRequest.current
    let stream: MediaStream | undefined
    setBusy('voice-recording')
    try {
      stream = await openMicrophone({ echoCancellation: true, noiseSuppression: true, autoGainControl: true })
      if (request !== audioRequest.current) { stream.getTracks().forEach(track => track.stop()); return }
      const recorder = new MediaRecorder(stream)
      const chunks: Blob[] = []
      recorder.ondataavailable = event => { if (event.data.size) chunks.push(event.data) }
      recorder.onstop = async () => {
        window.clearTimeout(audioTimer.current)
        localReader.current?.(); localReader.current = null
        recorder.stream.getTracks().forEach(track => track.stop())
        setRecording(false)
        try {
          const blob = new Blob(chunks, { type: recorder.mimeType || 'audio/webm' })
          const sample = await asDataUrl(blob)
          if (request === audioRequest.current) await addVoice(sample, blob.type)
        } catch { if (request === audioRequest.current) setNotice('Não foi possível ler a gravação. Tente novamente.') }
        finally { if (request === audioRequest.current) { audioPending.current = false; setBusy('') } }
      }
      recorderRef.current = recorder; recorder.start(); setRecording(true); setReadWords([]); setNotice('Leia a frase por inteiro, com voz natural. A gravação termina em até 12 segundos.')
      const readingError = () => {
        if (request === audioRequest.current && recorder.state === 'recording') setNotice('Destaque local indisponível. Você ainda pode concluir a gravação.')
      }
      void followLocalReading(stream, text => {
        if (request === audioRequest.current && recorder.state === 'recording') setReadWords(findReadWords(enrollmentPhrase, text))
      }, readingError).then(cleanup => {
        if (request !== audioRequest.current || recorder.state !== 'recording') cleanup()
        else localReader.current = cleanup
      }).catch(readingError)
      audioTimer.current = window.setTimeout(() => { if (recorder.state === 'recording') recorder.stop() }, 12000)
    } catch {
      stream?.getTracks().forEach(track => track.stop())
      audioPending.current = false; setBusy(''); setRecording(false)
      setNotice('Permissão de microfone negada ou indisponível.')
    }
  }
  const stopVoice = () => { if (recorderRef.current?.state === 'recording') { recorderRef.current.stop(); setRecording(false) } }

  const openCamera = async (cameraId = selectedCameraId) => {
    faceRequest.current++
    const request = ++cameraRequest.current
    try {
      streamRef.current?.getTracks().forEach(track => track.stop())
      const stream = await openConfiguredCamera(cameraId || undefined)
      if (request !== cameraRequest.current) { stream.getTracks().forEach(track => track.stop()); return }
      streamRef.current = stream
      if (videoRef.current) videoRef.current.srcObject = stream
      setCameraOpen(true)
      await refreshCameraDevices()
    } catch { setNotice('Permissão de câmera negada ou indisponível.') }
  }
  const captureFace = async (verify = false, access = false) => {
    const video = videoRef.current
    if (!video || video.readyState < 2) { setNotice('A câmera ainda está iniciando.'); return }
    const canvas = document.createElement('canvas'); canvas.width = video.videoWidth; canvas.height = video.videoHeight; canvas.getContext('2d')?.drawImage(video, 0, 0)
    const sample = canvas.toDataURL('image/jpeg', 0.86)
    const request = ++faceRequest.current
    if (access) rememberIdentityEvidence()
    setBusy(verify ? 'verify-face' : 'face')
    try {
      const data = verify ? await call({ action: access ? 'verify_access' : 'verify', kind: 'face', sample, content_type: 'image/jpeg' }) : await call({ action: 'add_sample', profile_id: profileId, password: samplePassword, kind: 'face', sample, content_type: 'image/jpeg' })
      if (request !== faceRequest.current) return
      if (access) { rememberIdentityEvidence(data.matched && !data.requires_confirmation ? data.evidence_token : undefined); setNotice(data.matched && !data.requires_confirmation ? 'Rosto confirmado para o próximo pedido, por até 60 segundos.' : 'Rosto desconhecido. Acesso não autorizado.') }
      if (verify) setVerification({ kind: 'face', ...data }); else { setNotice('Foto de referência adicionada.'); await refresh() }
    } catch (error) { setNotice(error instanceof Error ? error.message : 'Falha na imagem.') }
    finally { setBusy('') }
  }
  const verifyVoice = async () => {
    if (busy || audioPending.current) return
    if (!navigator.mediaDevices?.getUserMedia) { setNotice('O microfone está indisponível neste navegador.'); return }
    setBusy('verify-voice')
    setVerification(null)
    audioPending.current = true
    const request = ++audioRequest.current
    let stream: MediaStream | undefined
    try {
      stream = await openMicrophone()
      if (request !== audioRequest.current) { stream.getTracks().forEach(track => track.stop()); return }
      const recorder = new MediaRecorder(stream); const chunks: Blob[] = []
      recorderRef.current = recorder
      recorder.ondataavailable = e => { if (e.data.size) chunks.push(e.data) }; recorder.onstop = async () => { window.clearTimeout(audioTimer.current); recorder.stream.getTracks().forEach(t => t.stop()); const blob = new Blob(chunks, { type: recorder.mimeType || 'audio/webm' }); setBusy('verify-voice'); try { const video = videoRef.current
        let image: string | undefined
        if (video && video.readyState >= 2) {
          const canvas = document.createElement('canvas'); canvas.width = video.videoWidth; canvas.height = video.videoHeight
          canvas.getContext('2d')?.drawImage(video, 0, 0); image = canvas.toDataURL('image/jpeg', 0.85)
        }
        const audio = await asDataUrl(blob)
        if (request !== audioRequest.current) return
        const result = await call({ action: 'observe', audio, image, content_type: blob.type })
        setVerification({ kind: 'voice', ...result.speaker })
        const visible = (result.visible_people || []).map((face: any) => face.matched && !face.requires_confirmation ? face.profile?.name : 'Pessoa não identificada').join(', ')
        const cameraResult = result.camera_error || (!image ? 'Câmera sem imagem.' : visible ? `Na câmera: ${visible}.` : 'Nenhum rosto detectado no quadro.')
        const speakerResult = result.speaker?.error || (result.speaker?.enabled === false ? 'Cadastre uma amostra de voz para identificar a pessoa.' : result.speaker?.matched && !result.speaker?.requires_confirmation ? `Voz de ${result.speaker.profile?.name}.` : 'Voz não confirmada.')
        setNotice([cameraResult, speakerResult].join(' '))
      } catch (e) { setNotice(e instanceof Error ? e.message : 'Falha na verificação.') } finally { audioPending.current = false; setBusy('') } }
      recorder.start(); setNotice('Fale agora por 3 segundos…'); audioTimer.current = window.setTimeout(() => { if (recorder.state === 'recording') recorder.stop() }, 3000)
    } catch { stream?.getTracks().forEach(track => track.stop()); audioPending.current = false; setBusy(''); setNotice('Confira a permissão e a disponibilidade do microfone.') }
  }

  useEffect(() => {
    if (!cameraOpen || !autoDetect) return
    const id = window.setInterval(() => { if (!busy) captureFace(true).catch(() => undefined) }, 5000)
    return () => window.clearInterval(id)
  }, [cameraOpen, autoDetect, busy])

  const selected = status.profiles?.find(profile => profile.id === profileId)
  return <section className="identity-page">
    <article className="identity-card"><h2>Cadastro guiado</h2><p>Você pode conversar com o Jarvis sem se identificar. Novos usuários não recebem acesso aos dados privados do administrador.</p><button disabled={!!busy} onClick={() => startIdentityEnrollment()}>Cadastrar minha identidade</button><button disabled={!!busy} onClick={() => startIdentityEnrollment({ admin: true })}>{status.has_admin ? 'Refazer meu cadastro de administrador' : 'Cadastrar administrador com senha de desbloqueio'}</button><p>O cadastro administrativo usa a mesma senha que desbloqueia o aplicativo. As biometrias de desbloqueio são configuradas separadamente.</p></article>
    <div className="identity-intro"><p className="eyebrow">SESSÃO DE TESTE · IDENTIDADE LOCAL</p><h2>Quem está falando com o Jarvis?</h2><button disabled={!!busy} onClick={async () => { setBusy('face-model'); try { const response = await fetch('/api/identity', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ action: 'face_model_install' }) }); const data = await response.json(); setNotice(data.ok ? 'Modelo facial local preparado. Recadastre rostos antigos e use várias amostras com iluminação diferente.' : data.error || 'Falha ao preparar modelo.'); } catch { setNotice('Não foi possível preparar o modelo facial.'); } finally { setBusy(''); } }}>Preparar reconhecimento facial local (gratuito)</button><p>Cadastre uma identidade com consentimento explícito. Voz e rosto ficam no computador e podem ser apagados pelo arquivo local de dados. O chat de texto desbloqueado pertence ao administrador principal. Na ligação, dados pessoais exigem a voz dele reconhecida; reconhecer um rosto serve para identificar quem aparece, sem liberar dados privados por voz.</p></div>
    <div className="identity-grid">
      <article className="identity-card"><span className="identity-step">{status.has_admin ? '01 · ACESSO ADMINISTRATIVO' : '01 · PRIMEIRO ADMINISTRADOR'}</span><h3>{status.has_admin ? 'Gerenciar pessoas' : 'Proteja o primeiro perfil'}</h3>{status.has_admin ? <><small>O administrador já existe. Use a senha abaixo somente para autorizar o cadastro de uma nova pessoa.</small><input value={name} onChange={e => setName(e.target.value)} placeholder="Nome da nova pessoa" /><input type="password" value={adminPassword} onChange={e => setAdminPassword(e.target.value)} placeholder="Senha de desbloqueio do aplicativo" autoComplete="current-password" /><button disabled={!!busy || !name || !adminPassword} onClick={enrollProfile}>{busy === 'profile' ? 'Criando…' : 'Adicionar pessoa'}</button></> : <><input value={name} onChange={e => setName(e.target.value)} placeholder="Nome para chamar" /><input type="password" value={password} onChange={e => setPassword(e.target.value)} placeholder="Senha de desbloqueio do aplicativo" autoComplete="current-password" /><button disabled={!!busy} onClick={enrollAdmin}>{busy === 'admin' ? 'Criando…' : 'Criar administrador'}</button></>}</article>
      <article className="identity-card"><span className="identity-step">02 · VOZ LOCAL</span><h3>Modelo de identificação</h3><p>{voiceModel.ready ? `Pronto no computador (${Math.round((voiceModel.model_size_bytes || 0) / 1024 / 1024)} MB).` : 'Ainda não preparado. O download é único e o reconhecimento funciona localmente.'}</p>{!voiceModel.ready && <button disabled={!!busy} onClick={installVoiceModel}>{busy === 'voice-model' ? 'Preparando…' : 'Preparar modelo de voz'}</button>}{voiceModel.ready && <label className="identity-auto"><input type="checkbox" checked={identifyInCalls} onChange={e => { setIdentifyInCalls(e.target.checked); localStorage.setItem('jarvis_speaker_identification', e.target.checked ? '1' : '0'); window.dispatchEvent(new CustomEvent('jarvis-speaker-preference', { detail: e.target.checked })) }} /> identificar a voz de cada turno nas ligações</label>}<small>Use 2–3 amostras de 3–5 segundos, uma pessoa por vez. Não reconhece vozes sobrepostas nesta primeira versão.</small></article>
      <article className="identity-card"><span className="identity-step">03 · PERFIL</span><h3>Amostras de referência</h3><select value={profileId} onChange={e => { setProfileId(e.target.value); setSamplePassword('') }}><option value="">Selecione um perfil</option>{status.profiles?.map(profile => <option key={profile.id} value={profile.id}>{profile.name} · {profile.role}</option>)}</select><input type="password" value={samplePassword} onChange={e => setSamplePassword(e.target.value)} placeholder="Senha de desbloqueio para as amostras" autoComplete="current-password" /><div className="identity-enrollment-phrase"><small>Leia naturalmente a frase abaixo. Palavras verdes foram percebidas como feedback e a transcrição não é salva.</small><p>{enrollmentPhrase.split(/\s+/).map((word, index) => <span key={`${word}-${index}`} style={{ color: readWords.includes(index) ? '#36e6a5' : undefined, transition: 'color 160ms ease' }}>{word} </span>)}</p><button type="button" disabled={recording} onClick={() => { setEnrollmentPhrase(chooseEnrollmentPhrase(enrollmentPhrase)); setReadWords([]) }}>↻ Trocar frase</button></div><select value={selectedCameraId} onChange={e => { setSelectedCameraId(e.target.value); if (cameraOpen) openCamera(e.target.value).catch(() => undefined) }} aria-label="Escolha a câmera"><option value="">Câmera padrão</option>{cameraDevices.map((camera, index) => <option key={camera.deviceId || index} value={camera.deviceId}>{camera.label}</option>)}</select><div className="identity-actions"><button disabled={!voiceModel.ready || !profileId || !samplePassword || !!busy || recording} onClick={startVoice}>{recording ? 'Gravando…' : 'Gravar leitura'}</button>{recording && <button type="button" onClick={stopVoice}>Encerrar leitura</button>}<button disabled={!profileId || !samplePassword || !!busy} onClick={() => openCamera()}>Abrir câmera escolhida</button><button disabled={!!busy} onClick={() => refreshCameraDevices().catch(() => setNotice('Não foi possível listar as câmeras.'))}>Atualizar lista</button></div>{selected && <p className="identity-meta">{selected.voice_samples || 0} voz · {selected.face_samples || 0} rosto</p>}</article>
    </div>
    {cameraOpen && <div className="identity-camera"><video ref={videoRef} autoPlay muted playsInline /><label className="identity-auto"><input type="checkbox" checked={autoDetect} onChange={e => setAutoDetect(e.target.checked)} /> detectar perfis conhecidos automaticamente a cada 5 s</label><div><button onClick={() => captureFace(false)} disabled={!!busy || !profileId || !samplePassword}>Salvar foto</button><button onClick={() => captureFace(true)} disabled={!!busy}>Verificar rosto</button><button onClick={() => captureFace(true, true)} disabled={!!busy}>Confirmar rosto para próximo pedido</button><button onClick={() => { cameraRequest.current++; faceRequest.current++; streamRef.current?.getTracks().forEach(t => t.stop()); streamRef.current = null; setCameraOpen(false); setAutoDetect(false) }}>Fechar</button></div></div>}
    <article className="identity-card identity-verify"><span className="identity-step">04 · TESTE</span><h3>Verificar sem conceder acesso automaticamente</h3><p>As pontuações medem similaridade, não porcentagem de certeza. Resultados próximos entre pessoas são recusados. Nenhuma identificação altera permissões.</p><div className="identity-actions"><button disabled={!voiceModel.ready || !!busy} onClick={verifyVoice}>Testar voz</button><button disabled={!!busy || !cameraOpen} onClick={() => captureFace(true)}>Testar rosto atual</button><button type="button" onClick={forgetActiveProfile}>Esquecer perfil ativo</button></div>{verification && <div className={`identity-result ${verification.matched ? 'matched' : 'unknown'}`}><strong>{verification.matched ? `${verification.requires_confirmation ? 'Voz provável' : 'Correspondência forte'}: ${verification.profile?.name}` : 'Pessoa não confirmada'}</strong><span>Similaridade: {(verification.confidence || 0).toFixed(3)}</span></div>}</article>
    {status.has_admin && <article className="identity-card"><h3>Níveis de acesso por voz</h3><p>O chat de texto desbloqueado tem acesso completo. Na voz, apenas o administrador principal reconhecido pode consultar suas conversas e memórias pessoais.</p><p>Visitante: conversa e câmeras. Usuário autorizado: criar alarmes, consultar clima com cidade informada, notícias e cotações, controlar mídia e volume. Administrador delegado: também brilho, telemetria, bloqueio de tela, calculadora e Paint. Esses níveis não liberam arquivos, mensagens, scripts ou dados pessoais.</p><input aria-label="Senha para permissões" type="password" value={adminPassword} onChange={e => setAdminPassword(e.target.value)} placeholder="Senha de desbloqueio do aplicativo" />{status.profiles?.filter(p => p.role !== 'admin').map(p => <label key={p.id}>{p.name}<select aria-label={`Nível de voz de ${p.name}`} disabled={!!busy || !adminPassword} value={p.command_level || 'visitor'} onChange={async e => { setBusy('permission'); try { await call({ action: 'set_permission', profile_id: p.id, level: e.target.value, admin_password: adminPassword }); await refresh(); setNotice('Nível de voz atualizado.') } catch (error) { setNotice(error instanceof Error ? error.message : 'Falha ao alterar nível.') } finally { setBusy('') } }}><option value="visitor">Visitante</option><option value="user">Usuário autorizado</option><option value="delegate">Administrador delegado</option></select></label>)}</article>}
    {notice && <p className="identity-notice">{notice}</p>}
  </section>
}
