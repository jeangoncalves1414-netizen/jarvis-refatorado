import { alignWords } from '../../utils/pronunciation'

export function PronunciationFeedback({ target, transcript, threshold = 80, onRepeat }: { target: string; transcript: string; threshold?: number; onRepeat: (text: string) => void }) {
  const words = alignWords(target, transcript)
  const weak = words.filter(word => word.score < threshold)
  return <section aria-label="Comparação por palavra">
    <p>Toque em uma palavra para ouvir a referência. A nota compara o texto reconhecido e não mede todos os sons fonéticos.</p>
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
      {words.map((word, index) => <button type="button" key={index} className={`lang-word-feedback ${word.score >= threshold ? 'lang-score-good' : word.score >= Math.max(50, threshold - 25) ? 'lang-score-ok' : 'lang-score-bad'}`}
        title={`Reconhecido: ${word.heard || 'não detectado'}`} onClick={() => onRepeat(word.word)}>
        {word.word} <small>{word.score}%</small>
      </button>)}
    </div>
    <p><b>Você disse:</b> {transcript || 'Nenhuma palavra detectada.'}</p>
    {weak.length > 0 && <button type="button" onClick={() => onRepeat(weak.map(word => word.word).join(' '))}>Ouvir e repetir palavras para melhorar</button>}
  </section>
}
