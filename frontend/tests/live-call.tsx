import { useEffect } from 'react'
import { createRoot } from 'react-dom/client'
import { LiveCallModal } from '../src/components/LiveCallModal'
import { useMediaAssistant } from '../src/hooks/useMediaAssistant'

function Harness() {
  const media = useMediaAssistant({ query: '', sessionId: 'e2e-session', sendText: async () => 'Resposta do fallback.', setQuery: () => {}, setAnswer: () => {}, appendExchange: async (user, reply, receipt) => { (window as any).savedExchange = { user, reply, receipt } } })
  useEffect(() => { media.setSpeakEnabled(true) }, [])
  return <>
    <button onClick={() => media.setLiveCallOpen(true)}>Abrir chamada</button>
    <button onClick={() => void media.cancelCurrentAction()}>Cancelar pedido</button>
    <input aria-label="Campo de texto" />
    <output data-testid="diagnostics">{JSON.stringify(media.liveAudioDiagnostics)}</output>
    <output data-testid="orb">{media.liveOrbState}</output>
    <LiveCallModal open={media.liveCallOpen} onClose={media.closeLiveCall} recording={media.liveCallRecording}
      status={media.liveCallStatus} userTranscript={media.liveUserTranscript} turns={media.liveTurns} orbState={media.liveOrbState}
      audioDiagnostics={media.liveAudioDiagnostics} onToggleCapture={media.toggleLiveCallCapture} onBargeIn={media.triggerBargeIn}
      pushToTalkMode={media.pushToTalkMode} onTogglePushToTalk={media.togglePushToTalk} onPttStart={media.startPtt} onPttEnd={media.stopPtt} isPttActive={media.isPttActive} />
  </>
}
createRoot(document.getElementById('root')!).render(<Harness />)
