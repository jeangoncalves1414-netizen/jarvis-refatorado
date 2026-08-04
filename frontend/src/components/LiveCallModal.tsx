import { motion } from 'framer-motion'
import { JarvisOrb } from './JarvisOrb'

type LiveCallModalProps = {
  open: boolean
  onClose: () => void
  recording: boolean
  status: string
  onToggleCapture: () => void
}

export function LiveCallModal({ open, onClose, recording, status, onToggleCapture }: LiveCallModalProps) {
  if (!open) return null

  return (
    <div className="tool-modal live-call-modal" role="dialog" aria-modal="true" aria-label="Modo ligação">
      <motion.section
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.28 }}
      >
        <button className="modal-close" onClick={onClose} aria-label="Encerrar ligação">×</button>
        <p className="eyebrow">MODO LIGAÇÃO</p>
        <JarvisOrb size={128} listening={recording} />
        <h2>Converse com o Jarvis</h2>
        <p>{status}</p>
        <button className={recording ? 'call-button recording' : 'call-button'} onClick={onToggleCapture}>
          {recording ? 'Parar e enviar' : 'Toque para falar'}
        </button>
        <small>O áudio é transcrito pelo mesmo serviço do painel e a resposta aparece no chat.</small>
      </motion.section>
    </div>
  )
}
