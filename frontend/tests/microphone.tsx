import { createRoot } from 'react-dom/client'
import { VoiceSettings } from '../src/components/VoiceSettings'

createRoot(document.getElementById('root')!).render(<VoiceSettings ttsSettings={null} sttSettings={null} oxyySettings={null} onSetTtsProvider={() => {}} onSetSttProvider={() => {}} onSaveOxyy={() => {}} />)
