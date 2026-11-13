import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import App from './App'
import { AppLockGate } from './components/AppLock'
import { isMobileStandalone } from './hooks/useDirectChat'
import { WindowProvider } from './windows/WindowManager'
import { PopupProvider } from './popups/PopupProvider'
import './memory-and-chat.css'
import './profile-memory.css'
import './camera-workspace.css'
import './styles.css'
import './styles/ws-tokens.css'
import './styles/workspace.css'
import './styles/settings.css'
import './styles/lifeos.css'
import './styles/command-palette.css'
import './styles/windows.css'
import './styles/popups.css'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <AppLockGate standalone={isMobileStandalone()}>
    <WindowProvider>
      <PopupProvider>
        <App />
      </PopupProvider>
    </WindowProvider>
    </AppLockGate>
  </StrictMode>,
)

// Register PWA Service Worker
if (typeof window !== 'undefined' && 'serviceWorker' in navigator && import.meta.env.PROD) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/sw.js', { updateViaCache: 'none' })
      .then(registration => registration.update())
      .catch(() => {
        /* ignore registration error */
      })
  })
}
