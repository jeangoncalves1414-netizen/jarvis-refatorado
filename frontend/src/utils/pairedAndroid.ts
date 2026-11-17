/** The installed Android app, whether paired locally or connected to the cloud. */
export const pairedAndroid = typeof document !== 'undefined' && !!document.querySelector(
  'meta[name="jarvis-paired-android"], meta[name="jarvis-mobile-android"]',
)

const MOBILE_LOCK_COOKIE = 'jarvis_mobile_lock'

function mobileLockCookie() {
  if (typeof document === 'undefined') return ''
  return document.cookie.split('; ').find(cookie => cookie.startsWith(`${MOBILE_LOCK_COOKIE}=`))?.split('=')[1] || ''
}

/** The paired phone may open without the desktop password, by the owner's choice. */
export function mobilePasswordRequired() {
  return !pairedAndroid || mobileLockCookie() !== 'off'
}

export function setMobilePasswordRequired(required: boolean) {
  if (!pairedAndroid || typeof document === 'undefined') return
  document.cookie = `${MOBILE_LOCK_COOKIE}=${required ? 'on' : 'off'}; Path=/; Max-Age=31536000; Secure; SameSite=Strict`
}
