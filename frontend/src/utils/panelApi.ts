export async function panelRequest<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, init)
  const data = await response.json().catch(() => null)
  if (!response.ok || data?.ok === false) throw new Error(data?.error || `Não foi possível concluir a solicitação (HTTP ${response.status}).`)
  if (!data || typeof data !== 'object') throw new Error('O servidor retornou uma resposta inválida.')
  return data as T
}
