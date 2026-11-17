import { useEffect } from 'react'
import { createRoot } from 'react-dom/client'
import { LiveCallModal } from '../src/components/LiveCallModal'
import { LiveEnrollment } from '../src/components/LiveEnrollment'
import { useMediaAssistant } from '../src/hooks/useMediaAssistant'
import { useChat } from '../src/hooks/useChat'

function Harness() {
  const chat = useChat()
  const media = useMediaAssistant({ query: '', sessionId: 'e2e-session', sendText: async () => 'Resposta do fallback.', setQuery: () => {}, setAnswer: () => {}, previewExchange: chat.previewExchange, appendExchange: async (user, reply, receipt, previewId) => {
    await chat.appendExchange(user, reply, receipt, previewId)
    ;(window as any).savedExchange = { user, reply, receipt }
  } })
  useEffect(() => { media.setSpeakEnabled(true) }, [])
  return <>
    <LiveEnrollment />
    <button onClick={() => media.setLiveCallOpen(true)}>Abrir chamada</button>
    <button onClick={() => void media.cancelCurrentAction()}>Cancelar pedido</button>
    <button onClick={() => void chat.createSession()}>Nova conversa de teste</button>
    <output data-testid="chat-messages">{JSON.stringify(chat.messages)}</output>
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
