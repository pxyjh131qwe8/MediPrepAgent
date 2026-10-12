import type { ConsultRequest, ConsultResponse } from './types'

const API_BASE = (import.meta.env.VITE_API_BASE_URL as string | undefined)?.replace(/\/$/, '') ?? ''

export async function checkServer(): Promise<boolean> {
  try {
    const response = await fetch(`${API_BASE}/health/ping`)
    return response.ok
  } catch {
    return false
  }
}

export async function consultHealth(payload: ConsultRequest): Promise<ConsultResponse> {
  const response = await fetch(`${API_BASE}/health/consult`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })

  if (!response.ok) {
    let message = '这次没有顺利完成，请稍后再试。'
    try {
      const data = await response.json()
      if (typeof data.detail === 'string') message = data.detail
    } catch {
      // Keep the friendly default when the server does not return JSON.
    }
    throw new Error(message)
  }

  return response.json() as Promise<ConsultResponse>
}
