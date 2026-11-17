// A fresh server handle is consumed once; selecting a profile is never proof.
let evidence: { token: string; expires: number } | undefined
export function rememberIdentityEvidence(token?: string) {
  evidence = token ? { token, expires: Date.now() + 55000 } : undefined
}
export function takeIdentityEvidence() {
  const value = evidence
  evidence = undefined
  return value && value.expires > Date.now() ? value.token : undefined
}
