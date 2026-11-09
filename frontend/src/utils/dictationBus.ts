// Ponte entre a ligação por voz e o popup de anotação ao vivo (lote 6).
// Durante uma ligação, o popup que está gravando registra um destino aqui; a ligação entrega as
// falas a ele em vez de mandá-las ao agente, até a usuária dizer "fim da nota" ou clicar em Parar.

export type DictationSink = { onPhrase: (text: string) => void; onInterim: (text: string) => void }

let sink: DictationSink | null = null
let callProbe: (() => boolean) | null = null

export const liveDictationBus = {
  sink: () => sink,
  setSink: (next: DictationSink | null) => { sink = next },
  // A ligação informa se está ouvindo; sem ligação ativa, o popup usa o próprio microfone.
  setCallProbe: (probe: (() => boolean) | null) => { callProbe = probe },
  callActive: () => Boolean(callProbe?.()),
}
