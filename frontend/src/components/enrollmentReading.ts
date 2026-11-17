const ENROLLMENT_PHRASES = [
  'Jarvis registra minha voz com clareza enquanto leio esta frase calma, natural e contínua para criar uma referência pessoal mais estável.',
  'Hoje eu falo em um ritmo confortável e com volume normal para criar uma referência segura da minha voz neste computador.',
  'A identificação local aprende características da minha fala enquanto eu leio esta frase inteira sem guardar a gravação original depois do processamento.',
  'Eu confirmo que autorizo o Jarvis a usar esta amostra para reconhecer minha voz durante conversas locais e nunca como senha de segurança.',
]

export function isAdminEnrollmentRequest(text: string) {
  const request = text.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase().trim()
    .replace(/^(?:(?:oi|ola|jarvis|por favor)[\s,!:]+)+/, '').replace(/[.!?]+$/, '').trim()
  if (/^(?:(?:eu )?(?:quero|preciso|gostaria de) )?(?:iniciar|comecar) como (?:admin|administrador[a]?)$/.test(request)) return true
  if (/\b(?:posso|poderia) (?:colocar|digitar|inserir) (?:a |minha )?senha\b/.test(request)
    && /\b(?:para|pra) (?:mim|eu) (?:conseguir )?iniciar o (?:re)?cadastro (?:aqui )?como (?:admin|administrador[a]?)$/.test(request)) return true
  return enrollmentIntent(request) && /\b(?:admin|administrador|administradora)\b/.test(request)
    && /\b(?:me|meu|minha|eu|registro|cadastro|recadastro)\b/.test(request)
}

function enrollmentIntent(text: string) {
  const request = text.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase()
  if (/\b(?:nao|nunca|como faco|como funciona|explique|exemplo|se eu|quando eu)\b/.test(request)) return false
  if (/\be\s+(?:revel\w*|exclu\w*|apag\w*|mostr\w*|abr\w*|fech\w*)\b/.test(request)) return false
  const registration = /\b(?:registr\w*|cadastr\w*|recadastr\w*)\b/.test(request)
  const asking = /\b(?:quero|preciso|gostaria|pode|poderia|vamos|tenta|tente|refaz|refaca|refazer|inici\w*|comec\w*|abr[ae]|usar|use|faz|faca)\b/.test(request)
  return registration && (asking || /\b(?:(?:me )?(?:registr[ae]|cadastr[ae]|recadastr[ae])(?:-me)?|me registrar|me cadastrar)\b/.test(request))
}

export function parseSelfEnrollment(text: string): { name?: string; admin: boolean } | null {
  let request = text.trim().replace(/^(?:(?:oi|ol[aá]|jarvis|por favor)(?=[\s,!:]|$)[\s,!:]*)+/iu, '')
  let name: string | undefined
  const introduction = request.match(/^(?:(?:eu\s+)?sou(?:\s+[oa])?|meu nome [ée]|me chamo)\s+([\p{L}][\p{L}' -]{0,79}?)(?:[,!.?]+\s*|\s+(?:e\s+)?)(?=(?:jarvis\b|pode\b|poderia\b|quero\b|preciso\b|gostaria\b|me\b|cadastre\b|registre\b))/iu)
  if (introduction) { name = introduction[1].trim(); request = request.slice(introduction[0].length) }
  request = request.replace(/^(?:jarvis[,! ]+)/iu, '')
    .replace(/[, ]+por favor[.!?]*$/iu, '')
    .replace(/^(?:eu )?(?:quero|gostaria) que (?:voc[eê]|vc) /iu, '')
  if (isAdminEnrollmentRequest(request)) return { name, admin: true }
  if (enrollmentIntent(request) && (/\b(?:me|meu|minha|eu|mim)\b/i.test(request)
    || /^(?:(?:quero|pode) )?(?:iniciar|abrir|refazer|começar) (?:o )?(?:re)?cadastro[.!?]*$/iu.test(request))) return { name, admin: false }
  return null
}

export function parsePersonIntroduction(text: string): string | null {
  if (/\b(?:não|nao|nunca)\b/iu.test(text)) return null
  const match = text.trim().match(/(?:\b(?:quero\s+)?(?:te\s+)?apresent(?:ar|o)\s+|\b(?:ess[ae]|est[ae])(?:\s+aqui)?\s+é\s+)(?:(?:a|o)\s+)?(?:(?:minha|meu)\s+(?:irmã[o]?|amig[ao]|mãe|pai|prim[ao]|espos[ao]|filh[ao])[,\s]+)?(?:(?:a|o)\s+)?([\p{L}][\p{L}' -]{0,60}?)[.!?]*$/iu)
  return match?.[1].trim() || null
}

export function enrollmentModality(text: string): 'voice' | 'face' | 'both' | null {
  const answer = text.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase()
  if (/\b(?:nao|cancel\w*)\b/.test(answer)) return null
  const voice = /\bvoz\b/.test(answer), face = /\b(?:rosto|face)\b/.test(answer)
  return /\b(?:dois|ambos|tudo)\b/.test(answer) || (voice && face) ? 'both' : voice ? 'voice' : face ? 'face' : null
}

export function chooseEnrollmentPhrase(previous = '') {
  const options = ENROLLMENT_PHRASES.filter(phrase => phrase !== previous)
  return options[Math.floor(Math.random() * options.length)] || ENROLLMENT_PHRASES[0]
}

export const MIN_READING_COVERAGE = 0.80

function normalizeWords(value: string) {
  return value.normalize('NFKD').replace(/[\u0300-\u036f]/g, '').toLowerCase().match(/[a-z0-9]+/g) || []
}

export function findReadWords(phrase: string, heard: string) {
  const expected = normalizeWords(phrase)
  const spoken = new Map<string, number>()
  for (const word of normalizeWords(heard)) spoken.set(word, (spoken.get(word) || 0) + 1)
  const matched: number[] = []
  expected.forEach((word, index) => {
    const count = spoken.get(word) || 0
    if (count > 0) { matched.push(index); spoken.set(word, count - 1) }
  })
  return matched
}

export function asDataUrl(blob: Blob): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onerror = () => reject(new Error('Não foi possível ler a amostra.'))
    reader.onload = () => resolve(String(reader.result))
    reader.readAsDataURL(blob)
  })
}

