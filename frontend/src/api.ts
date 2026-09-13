export async function api<T>(path: string, init: RequestInit = {}, key?: string): Promise<T> {
  const headers = new Headers(init.headers)
  if (key?.trim()) headers.set('X-OpenAI-Key', key.trim())
  if (typeof init.body === 'string') headers.set('Content-Type', 'application/json')
  let response: Response
  try {
    response = await fetch(`/api${path}`, { ...init, headers, credentials: 'same-origin' })
  } catch {
    throw new Error('Could not reach your swim coach. Check that the app is running and try again.')
  }
  if (!response.ok) {
    const error = await response.json().catch(() => ({}))
    throw new Error(typeof error.detail === 'string' ? error.detail : 'Something in this request needs a second look. Check your settings and try again.')
  }
  return response.json() as Promise<T>
}

export async function downloadReport(): Promise<void> {
  const response = await fetch('/api/report', { credentials: 'same-origin' })
  if (!response.ok) {
    const error = await response.json().catch(() => ({}))
    throw new Error(error.detail || 'Your report could not be downloaded. Please try again.')
  }
  // Use a native same-origin download, including in browsers that cannot save blob URLs.
  // The first request validates the session so failures can stay in the app.
  await response.body?.cancel()
  const link = document.createElement('a')
  link.href = '/api/report'
  link.download = 'swim_analysis_report.md'
  document.body.appendChild(link)
  link.click()
  link.remove()
}
