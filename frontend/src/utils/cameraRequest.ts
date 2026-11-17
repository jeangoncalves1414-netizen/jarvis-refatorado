/** Only explicit requests to observe the current camera should start capture. */
export function isCameraObservationRequest(message: string, previousMessage = ''): boolean {
  const text = message.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase().trim()
  if (/\b(?:nao|nunca|sem|ontem|gravacao|historico|configuracao|permissao|configurar|instalar|driver)\b/.test(text)) return false
  if (!/\b(?:cameras?|webcams?)\b/.test(text)) {
    return Boolean(previousMessage) && isCameraObservationRequest(previousMessage) && /^(?:(?:e|jarvis|agora|ai|entao)[ ,]+)*(?:quem (?:voce )?(?:ve|esta vendo|consegue ver)|o que (?:voce )?(?:ve|esta vendo)|(?:olha|veja|tenta|tente|confere|analisa) (?:de novo|novamente)|e agora|agora)[?!. ]*$/.test(text)
  }
  if (/\b(?:us[ae]r?|tenta|tente)\b.*\b(?:ferramenta|camera)\b/.test(text)) return true
  const request = text.replace(/^(?:(?:oi|ola|jarvis|por favor|voce|vc|pode|poderia|consegue|conseguiria)\b[\s,!:?-]*)+/, '')
  return /^(?:me\s+)?(?:fala|fale|falar|diga|dizer)\b.*\b(?:quem|o que)\b/.test(request)
    || /^(?:me\s+)?(?:identifica|identifique|identificar|reconhece|reconheca|reconhecer)\b/.test(request)
    || /^(?:ver|ve|veja|vendo|enxergar|enxerga|olha|olhe|olhar|confere|conferir|verifica|verifique|verificar|mostra|mostre|mostrar|descreva|descrever|analisa|analise|analisar)\b/.test(request)
    || /^(?:esta|ta) vendo\b/.test(request)
    || /^(?:quem|o que|tem alguem|ha alguem|existe alguem)\b/.test(request)
}

export function isCameraPanelRequest(message: string): boolean {
  const text = message.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase()
  return !/\b(?:nao|sem)\b/.test(text) && /\b(?:abr[ae]|abrir|mostr[ae])\s+(?:(?:o|as)\s+)?(?:(?:painel|janela|tela)\s+(?:de|das)\s+)?cameras?\b/.test(text)
}

export async function requestVoiceCamera(message: string): Promise<string | null> {
  // The app resolves follow-ups against the current chat, including spoken turns.
  return new Promise(resolve => {
    const event = new CustomEvent('jarvis-request-camera', { detail: { message, resolve }, cancelable: true })
    if (window.dispatchEvent(event)) resolve(null)
  })
}
