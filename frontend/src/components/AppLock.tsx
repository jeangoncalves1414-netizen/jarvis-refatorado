import { mobilePasswordRequired, pairedAndroid, setMobilePasswordRequired } from '../utils/pairedAndroid'
import { openMicrophone } from '../utils/micPrefs'
import { useEffect, useRef, useState, type ReactNode } from 'react'
import { panelRequest } from '../utils/panelApi'
import { openConfiguredCamera } from '../utils/cameraCatalog'
import { rememberIdentityEvidence } from '../utils/identityEvidence'
import './appLock.css'

type Status = { configured: boolean; enabled: boolean; unlocked: boolean; face: boolean; voice: boolean }
const endpoint = '/api/app-lock'
async function request(data: Record<string, unknown>) {
  return panelRequest(endpoint, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data) })
}

function BiometricCapture({ kind, onSample, onCancel }: { kind: 'face' | 'voice'; onSample: (sample: string, content_type: string) => Promise<void>; onCancel: () => void }) {
  const video = useRef<HTMLVideoElement>(null)
  const stream = useRef<MediaStream | null>(null)
  const recorder = useRef<MediaRecorder | null>(null)
  const generation = useRef(0)
  const timer = useRef<number | undefined>(undefined)
  const [ready, setReady] = useState(false)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  useEffect(() => {
    const id = ++generation.current
    setReady(false); setBusy(false); setSubmitting(false); setError('')
    const open = async () => kind === 'face' ? openConfiguredCamera() : openMicrophone()
    void open().then(media => {
      if (id !== generation.current) { media.getTracks().forEach(track => track.stop()); return }
      stream.current = media
      if (video.current) video.current.srcObject = media
      setReady(true)
    }).catch(error => { if (id === generation.current) setError(error instanceof Error ? error.message : 'Não foi possível acessar a câmera ou o microfone. Verifique a permissão.') })
    return () => {
      generation.current++; window.clearTimeout(timer.current)
      if (recorder.current?.state === 'recording') recorder.current.stop()
      stream.current?.getTracks().forEach(track => track.stop())
      stream.current = null; recorder.current = null
    }
  }, [kind])
  const capture = async () => {
    if (!ready || busy) return
    const id = generation.current
    setBusy(true); setError('')
    try {
      if (kind === 'face') {
        const element = video.current!
        if (!element.videoWidth) throw new Error('Aguarde a imagem da câmera.')
        const canvas = document.createElement('canvas')
        canvas.width = element.videoWidth; canvas.height = element.videoHeight
        canvas.getContext('2d')!.drawImage(element, 0, 0)
        setSubmitting(true)
        await onSample(canvas.toDataURL('image/jpeg', 0.85), 'image/jpeg')
      } else {
        const blob = await new Promise<Blob>((resolve, reject) => {
          const rec = new MediaRecorder(stream.current!)
          let recordingTimer: number | undefined
          recorder.current = rec
          const chunks: BlobPart[] = []
          rec.ondataavailable = event => chunks.push(event.data)
          rec.onerror = () => reject(new Error('Falha ao gravar voz.'))
          rec.onstop = () => { window.clearTimeout(recordingTimer); resolve(new Blob(chunks, { type: rec.mimeType })) }
          rec.start()
          recordingTimer = window.setTimeout(() => { if (rec.state === 'recording') rec.stop() }, 5000)
          timer.current = recordingTimer
        })
        if (id !== generation.current) return
        const sample = await new Promise<string>((resolve, reject) => {
          const reader = new FileReader(); reader.onload = () => resolve(String(reader.result)); reader.onerror = reject; reader.readAsDataURL(blob)
        })
        if (id !== generation.current) return
        setSubmitting(true)
        await onSample(sample, blob.type)
      }
    } catch (err) { if (id === generation.current) setError(err instanceof Error ? err.message : 'Falha na captura.') }
    finally { if (id === generation.current) { setBusy(false); setSubmitting(false) } }
  }
  return <div className="app-lock-capture">
    {kind === 'face' ? <video ref={video} autoPlay muted playsInline /> : <p>Fale uma frase por cinco segundos, em um ambiente silencioso.</p>}
    {error && <p role="alert">{error}</p>}
    <button disabled={!ready || busy} onClick={() => void capture()}>{busy ? 'Verificando…' : kind === 'face' ? 'Capturar rosto' : 'Gravar voz'}</button>
    <button disabled={submitting} onClick={onCancel}>Cancelar</button>
  </div>
}

export function AppLockGate({ children, standalone = false }: { children: ReactNode; standalone?: boolean }) {
  if (standalone || (pairedAndroid && !mobilePasswordRequired())) return <>{children}</>
  return <LocalAppLockGate>{children}</LocalAppLockGate>
}

function LocalAppLockGate({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<Status | null>(null)
  const [password, setPassword] = useState('')
  const [confirmation, setConfirmation] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [kind, setKind] = useState<'face' | 'voice' | null>(null)
  const statusRequest = useRef(0)
  const refresh = async () => {
    const id = ++statusRequest.current
    try {
      const next = await panelRequest<Status>(endpoint)
      if (id !== statusRequest.current) return
      if (!next.configured || (next.enabled && !next.unlocked)) rememberIdentityEvidence()
      setStatus(next)
    } catch (err) {
      if (id !== statusRequest.current) return
      rememberIdentityEvidence(); setStatus(null); setError(err instanceof Error ? err.message : 'Falha ao consultar o bloqueio.')
    }
  }
  useEffect(() => { void refresh(); const interval = window.setInterval(() => void refresh(), 10000); return () => { statusRequest.current++; clearInterval(interval) } }, [])
  const act = async (payload: Record<string, unknown>) => {
    statusRequest.current++
    setBusy(true); setError('')
    try { await request(payload); setPassword(''); setConfirmation(''); setKind(null); await refresh() }
    catch (err) { setError(err instanceof Error ? err.message : 'Falha ao desbloquear.'); throw err }
    finally { setBusy(false) }
  }
  if (status?.configured && (!status.enabled || status.unlocked)) return <>{children}</>
  return <main className="app-lock"><section className="app-lock-card">
    <h1>{status?.configured ? 'Desbloquear Jarvis' : 'Proteja seu Jarvis'}</h1>
    {!status ? <><p>{error || 'Conectando ao Jarvis…'}</p><button onClick={() => void refresh()}>Tentar novamente</button></> : <>
      <p>{status.configured ? 'Digite sua senha para abrir o app.' : 'Escolha sua senha. Você poderá alterá-la, desativá-la ou cadastrar rosto e voz nas configurações.'}</p>
      <form onSubmit={event => { event.preventDefault(); if (!status.configured && password !== confirmation) { setError('As senhas não coincidem.'); return }; void act({ action: status.configured ? 'unlock' : 'setup', password }).catch(() => undefined) }}>
        <label>Senha<input autoFocus type="password" autoComplete={status.configured ? 'current-password' : 'new-password'} minLength={status.configured ? undefined : 8} maxLength={1024} required value={password} onChange={event => setPassword(event.target.value)} /></label>
        {!status.configured && <label>Confirmar senha<input type="password" autoComplete="new-password" required value={confirmation} onChange={event => setConfirmation(event.target.value)} /></label>}
        <button disabled={busy}>{busy ? 'Aguarde…' : status.configured ? 'Desbloquear' : 'Criar senha'}</button>
      </form>
      {!status.configured && <button disabled={busy} onClick={() => void act({ action: 'skip' }).catch(() => undefined)}>Configurar depois</button>}
      {!pairedAndroid && status.face && <button disabled={busy} onClick={() => setKind('face')}>Usar rosto</button>}
      {!pairedAndroid && status.voice && <button disabled={busy} onClick={() => setKind('voice')}>Usar voz</button>}
      {kind && <BiometricCapture kind={kind} onCancel={() => setKind(null)} onSample={(sample, content_type) => act({ action: 'biometric', kind, sample, content_type })} />}
      {error && <p role="alert">{error}</p>}
    </>}
  </section></main>
}

export function AppLockSettings() {
  const [status, setStatus] = useState<Status | null>(null)
  const [password, setPassword] = useState('')
  const [next, setNext] = useState('')
  const [confirmation, setConfirmation] = useState('')
  const [notice, setNotice] = useState('')
  const [busy, setBusy] = useState(false)
  const [consent, setConsent] = useState(false)
  const [kind, setKind] = useState<'face' | 'voice' | null>(null)
  const [pending, setPending] = useState<'face' | 'voice' | 'remove_biometrics' | null>(null)
  const [mobilePassword, setMobilePassword] = useState(() => mobilePasswordRequired())
  const refresh = () => panelRequest<Status>(endpoint).then(setStatus).catch(err => setNotice(err.message))
  useEffect(() => { void refresh() }, [])
  const act = async (action: string, extra: Record<string, unknown> = {}) => {
    setBusy(true); setNotice('')
    try {
      await request({ action, password, new_password: next, consent, ...extra })
      setPassword(''); setNext(''); setConfirmation(''); setKind(null); setNotice('Configuração atualizada.'); await refresh()
      if (action === 'lock') window.location.reload()
    } catch (err) { setNotice(err instanceof Error ? err.message : 'Falha ao salvar.'); throw err }
    finally { setBusy(false) }
  }
  const authorizeBiometrics = async () => {
    if (!pending || busy || !password) return
    setBusy(true); setNotice('')
    try {
      if (pending === 'remove_biometrics') await act('remove_biometrics')
      else { await request({ action: 'verify_password', password }); setKind(pending) }
      setPending(null)
    } catch (err) { setPassword(''); setNotice(err instanceof Error ? err.message : 'Não foi possível confirmar a senha.') }
    finally { setBusy(false) }
  }
  if (pairedAndroid) return <article className="settings-card app-lock-settings">
    <h2>Senha no celular</h2>
    <p>{mobilePassword ? 'O celular pede a senha do Jarvis ao abrir.' : 'Este celular abre direto. O pareamento seguro do aparelho continua obrigatório.'}</p>
    <label><input type="checkbox" checked={mobilePassword} onChange={event => {
      const required = event.target.checked
      setMobilePasswordRequired(required)
      setMobilePassword(required)
      setNotice(required ? 'A senha será solicitada na próxima abertura.' : 'O celular abrirá sem senha daqui em diante.')
      window.setTimeout(() => window.location.reload(), 250)
    }} /> Pedir senha ao abrir o Jarvis neste celular</label>
    <p>Rosto e voz não são usados neste aparelho.</p>
    <p role="status">{notice}</p>
  </article>
  return <article className="settings-card app-lock-settings">
    <h2>Bloqueio de abertura</h2><p>{status?.enabled ? 'Senha ativada. O app inicia bloqueado.' : 'Senha desativada.'}</p>
    <form onSubmit={event => { event.preventDefault(); if (next !== confirmation) { setNotice('As senhas não coincidem.'); return }; void act('change').catch(() => undefined) }}>
      {status?.enabled && <label>Senha atual<input type="password" autoComplete="current-password" value={password} onChange={event => setPassword(event.target.value)} /></label>}
      <label>Nova senha<input type="password" minLength={8} maxLength={1024} autoComplete="new-password" required value={next} onChange={event => setNext(event.target.value)} /></label>
      <label>Confirmar nova senha<input type="password" autoComplete="new-password" required value={confirmation} onChange={event => setConfirmation(event.target.value)} /></label>
      <button disabled={busy}>{status?.enabled ? 'Trocar senha' : 'Ativar senha'}</button>
    </form>
    {status?.enabled && <>
      <button disabled={busy} onClick={() => void act('lock').catch(() => undefined)}>Bloquear agora</button>
      <button disabled={busy || !password} onClick={() => void act('disable').catch(() => undefined)}>Desativar bloqueio com a senha atual</button>
      {!pairedAndroid && <><p>Rosto e voz são opções de conveniência. Esta verificação local pode aceitar fotos ou gravações e não substitui a segurança da senha. Os dados biométricos ficam neste computador.</p>
      <label><input type="checkbox" checked={consent} onChange={event => setConsent(event.target.checked)} /> Entendo essa limitação e quero usar biometria.</label>
      <p>Estas amostras desbloqueiam o aplicativo. Para o Jarvis reconhecer você na conversa, cadastre seu perfil em Identidade.</p>
      <button disabled={!consent || busy || !!kind} onClick={() => { setPassword(''); setPending('face') }}>{status.face ? 'Recadastrar rosto' : 'Cadastrar rosto'}</button>
      <button disabled={!consent || busy || !!kind} onClick={() => { setPassword(''); setPending('voice') }}>{status.voice ? 'Recadastrar voz' : 'Cadastrar voz'}</button>
      <button disabled={busy || !!kind} onClick={() => { setPassword(''); setPending('remove_biometrics') }}>Remover biometrias</button>
      {pending && <div className="enrollment-overlay"><section className="app-lock-card" role="dialog" aria-modal="true" aria-label="Autorizar biometria"><form onSubmit={event => { event.preventDefault(); void authorizeBiometrics() }}><h3>Confirme a senha de desbloqueio</h3><p>{pending === 'remove_biometrics' ? 'Autorize a remoção das biometrias de desbloqueio.' : 'Após confirmar a senha, iniciaremos a captura.'}</p><label>Senha de desbloqueio<input autoFocus required type="password" maxLength={1024} autoComplete="current-password" value={password} disabled={busy} onChange={event => setPassword(event.target.value)} /></label><button disabled={busy || !password}>Confirmar senha</button><button type="button" disabled={busy} onClick={() => { setPending(null); setPassword(''); setNotice('') }}>Cancelar</button><p role="alert">{notice}</p></form></section></div>}
      {kind && <BiometricCapture kind={kind} onCancel={() => { setKind(null); setPassword('') }} onSample={(sample, content_type) => act('enroll', { kind, sample, content_type })} />}</>}
    </>}
    <p role="status">{notice}</p>
  </article>
}
