import { alignWords } from '../../utils/pronunciation'

export function PronunciationFeedback({ target, transcript, threshold = 80, onRepeat }: { target: string; transcript: string; threshold?: number; onRepeat: (text: string) => void }) {
  const words = alignWords(target, transcript)
  return <section className="lang-feedback-phrase" aria-label="Comparação por palavra">
    {words.map((word, index) => <button type="button" key={index} className={`lang-word-feedback ${word.score >= threshold ? 'lang-score-good' : word.score >= Math.max(50, threshold - 25) ? 'lang-score-ok' : 'lang-score-bad'}`}
        title={`Reconhecido: ${word.heard || 'não detectado'}`} onClick={() => onRepeat(word.word)}>
        {word.word}
      </button>)}
  </section>
}
