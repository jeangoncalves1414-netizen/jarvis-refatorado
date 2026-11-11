// Converte o código curto do idioma-alvo (ex.: 'es') na tag BCP-47 usada pela Web Speech API
// e no nome em português exibido na interface.
const SPEECH_TAGS: Record<string, string> = {
  en: 'en-US',
  es: 'es-ES',
  fr: 'fr-FR',
  de: 'de-DE',
  it: 'it-IT',
  pt: 'pt-BR',
  ja: 'ja-JP',
  ko: 'ko-KR',
  zh: 'zh-CN',
  ru: 'ru-RU',
}

const LANGUAGE_NAMES: Record<string, string> = {
  en: 'inglês',
  es: 'espanhol',
  fr: 'francês',
  de: 'alemão',
  it: 'italiano',
  pt: 'português',
  ja: 'japonês',
  ko: 'coreano',
  zh: 'chinês',
  ru: 'russo',
}

export function speechLang(code?: string): string {
  const clean = (code || '').trim()
  if (!clean) return 'en-US'
  if (clean.includes('-')) return clean
  return SPEECH_TAGS[clean.toLowerCase()] || clean
}

export function languageName(code?: string): string {
  const clean = (code || '').trim()
  const base = clean.split('-')[0].toLowerCase()
  return LANGUAGE_NAMES[base] || clean || 'inglês'
}
