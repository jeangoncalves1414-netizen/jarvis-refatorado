import { useState } from 'react'

const levels = ['A1','A2','B1','B2','C1','C2']
const topics = ['Apresentações e necessidades básicas', 'Rotina, compras e viagens', 'Experiências e opiniões', 'Argumentação e hipóteses', 'Registro, inferência e precisão', 'Nuance, ironia e reformulação']
const items = [
  [['I ___ a student.', 'am', 'is', 'be'], ['She ___ two brothers.', 'has', 'have', 'having']],
  [['We ___ the museum yesterday.', 'visited', 'visit', 'visiting'], ['How ___ water do you need?', 'much', 'many', 'few']],
  [['I have lived here ___ 2018.', 'since', 'for', 'during'], ['If I had time, I ___ join you.', 'would', 'will', 'did']],
  [['By the time we arrived, the train ___.', 'had left', 'has left', 'has been leaving'], ['I wish I ___ that email yesterday.', 'had sent', 'send', 'have sent']],
  [['Scarcely ___ when the alarm sounded.', 'had she arrived', 'she had arrived', 'did she arriving'], ['His praise was qualified. What does that imply?', 'He expressed reservations.', 'He certified a qualification.', 'He agreed unconditionally.']],
  [['“Damning with faint praise” suggests…', 'criticism conveyed through lukewarm approval.', 'a sincere compliment expressed quietly.', 'explicit condemnation followed by praise.'], ['“It was not for want of trying” implies…', 'Effort was made despite the outcome.', 'The effort was unnecessary.', 'Nobody wanted to try.']],
]
type Round = { low:number; high:number; level:number; item:number }
const start = {low:-1, high:6, level:2, item:0}
export function Curriculum({level, english, apply}: {level:string; english:boolean; apply:(level:string)=>Promise<void>}) {
  const [round,setRound] = useState<Round|null>(null)
  const [result,setResult] = useState('')
  const [saving,setSaving] = useState(false)
  const [error,setError] = useState('')
  function answer(correct:boolean) {
    if (!round) return
    if (correct && round.item === 0) {setRound({...round,item:1}); return}
    const low = correct ? round.level : round.low
    const high = correct ? round.high : round.level
    if (high - low <= 1) {setResult(levels[Math.max(0,low)]); setRound(null)}
    else setRound({low, high, level:Math.floor((low+high)/2),item:0})
  }
  const question = round && items[round.level][round.item]
  return <details><summary>Trilha CEFR e nivelamento</summary>
    <ol>{levels.map((l,i) => <li key={l} aria-current={level === l ? 'step' : undefined}><b>{l}</b> · {topics[i]} {level === l && '← nível atual'}</li>)}</ol>
    {english && (!round ? <button onClick={() => {setRound(start);setResult('');setError('')}}>Fazer teste adaptativo de inglês</button>
      : question && <fieldset><legend>{question[0]}</legend>{[0,1,2].map(i => {
        const idx = (i+round.level+round.item)%3+1
        return <button key={idx} onClick={() => answer(idx===1)}>{question[idx]}</button>
      })}</fieldset>)}
    {result && <p>Nível de prática sugerido pela triagem de leitura: {result}. <button disabled={saving} onClick={async () => {
      setSaving(true)
      try {await apply(result);setResult('')} catch {setError('Falha ao salvar o nível. Tente novamente.')} finally {setSaving(false)}
    }}>Usar este nível</button></p>}
    {error && <p role="alert">{error}</p>}
  </details>
}
