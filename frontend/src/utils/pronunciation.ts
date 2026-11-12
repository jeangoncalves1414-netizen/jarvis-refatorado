export type WordMatch = { word: string; heard: string; score: number }

const normalize = (word: string) => word.toLocaleLowerCase().replace(/[^\p{L}\p{N}]/gu, '')

export function wordSimilarity(a: string, b: string): number {
  a = normalize(a); b = normalize(b)
  if (!a || !b) return 0
  let row = Array.from({ length: b.length + 1 }, (_, i) => i)
  for (let i = 1; i <= a.length; i++) {
    const next = [i]
    for (let j = 1; j <= b.length; j++) next[j] = Math.min(next[j - 1] + 1, row[j] + 1, row[j - 1] + Number(a[i - 1] !== b[j - 1]))
    row = next
  }
  return 1 - row[b.length] / Math.max(a.length, b.length)
}

// Alinhamento por sequência: uma omissão não desloca todas as palavras seguintes.
export function alignWords(target: string, transcript: string): WordMatch[] {
  const expected = target.trim().split(/\s+/).filter(Boolean).slice(0, 200)
  const spoken = transcript.trim().split(/\s+/).filter(Boolean).slice(0, 200)
  const costs = Array.from({ length: expected.length + 1 }, (_, i) => [i])
  costs[0] = Array.from({ length: spoken.length + 1 }, (_, i) => i)
  for (let i = 1; i <= expected.length; i++) {
    for (let j = 1; j <= spoken.length; j++) costs[i][j] = Math.min(
      costs[i - 1][j] + 1, costs[i][j - 1] + 1,
      costs[i - 1][j - 1] + 1 - wordSimilarity(expected[i - 1], spoken[j - 1]),
    )
  }
  const result: WordMatch[] = []
  let i = expected.length, j = spoken.length
  while (i || j) {
    if (i && j && Math.abs(costs[i][j] - (costs[i - 1][j - 1] + 1 - wordSimilarity(expected[i - 1], spoken[j - 1]))) < 1e-8) {
      result.unshift({ word: expected[--i], heard: spoken[--j], score: Math.round(wordSimilarity(expected[i], spoken[j]) * 100) })
    } else if (i && (!j || costs[i][j] === costs[i - 1][j] + 1)) {
      result.unshift({ word: expected[--i], heard: '', score: 0 })
    } else j--
  }
  return result
}
