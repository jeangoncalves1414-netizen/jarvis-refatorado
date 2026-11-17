import { useState } from 'react'
import { createRoot } from 'react-dom/client'
import { IdentityPage } from '../src/pages/IdentityPage'
import { CameraWorkspace } from '../src/components/CameraWorkspace'
import { AppLockGate, AppLockSettings } from '../src/components/AppLock'
import { LiveEnrollment } from '../src/components/LiveEnrollment'

function Harness() {
  const [open, setOpen] = useState(true)
  return <><button onClick={() => setOpen(false)}>Sair da identidade</button>{open && (location.search === '?settings' ? <AppLockSettings /> : location.search === '?enroll' ? <LiveEnrollment /> : location.search === '?lock' ? <AppLockGate><p>Painel desbloqueado</p></AppLockGate> : location.search === '?camera' ? <CameraWorkspace open onClose={() => setOpen(false)} onQuestion={async () => {}} /> : <IdentityPage />)}</>
}
createRoot(document.getElementById('root')!).render(<Harness />)
