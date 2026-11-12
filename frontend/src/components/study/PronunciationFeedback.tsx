import { alignWords } from '../../utils/pronunciation'

export function PronunciationFeedback({ target, transcript, onRepeat }: { target: string; transcript: string; onRepeat: (text: string) => void }) {
  const words = alignWords(target, transcript)
  const weak = words.filter(word => word.score < 80)
  return <section aria-label="Comparação por palavra">
    <p>Correspondência com o texto reconhecido — não mede precisão fonética.</p>
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
      {words.map((word, index) => <span key={index} className={word.score >= 80 ? 'lang-score-good' : word.score >= 50 ? 'lang-score-ok' : 'lang-score-bad'}
        title={`Reconhecido: ${word.heard || 'não detectado'}`}>
        {word.word} <small>{word.score}%</small>
      </span>)}
    </div>
    <p><b>Você disse:</b> {transcript || 'Nenhuma palavra detectada.'}</p>
    {weak.length > 0 && <button type="button" onClick={() => onRepeat(weak.map(word => word.word).join(' '))}>Ouvir e repetir palavras para melhorar</button>}
  </section>
}
