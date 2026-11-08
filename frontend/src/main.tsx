import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import App from './App'
import { WindowProvider } from './windows/WindowManager'
import './memory-and-chat.css'
import './profile-memory.css'
import './camera-workspace.css'
import './styles.css'
import './styles/workspace.css'
import './styles/windows.css'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <WindowProvider>
      <App />
    </WindowProvider>
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
