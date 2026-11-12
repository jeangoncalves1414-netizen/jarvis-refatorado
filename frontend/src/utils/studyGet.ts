/** Retry transient failures only for idempotent study reads. */
export async function studyGet(path: string, signal?: AbortSignal) {
  try {
    const response = await fetch(path, {signal})
    if (response.status < 500 && response.status !== 408) return response
  } catch (error) {
    if (signal?.aborted) throw error
  }
  return fetch(path, {signal})
}
