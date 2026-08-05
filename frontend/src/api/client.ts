import type {
  ChatCompletionResponse,
  ChatMessageIn,
  ChatSettings,
  HumanValidationCreateRequest,
  HumanValidationListResponse,
  HumanValidationPayload,
  IndexRebuildResponse,
  IndexStatusResponse,
  ModelsListResponse,
  PersonasListResponse,
  ScrapeResponse,
  UploadResponse,
} from './types'

const API_BASE = import.meta.env.VITE_API_BASE_URL || ''

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, init)
  if (!response.ok) {
    let detail = `Erro HTTP ${response.status}`
    try {
      const body = await response.json()
      detail = body.detail || detail
    } catch {
      /* ignore */
    }
    throw new Error(typeof detail === 'string' ? detail : JSON.stringify(detail))
  }
  return response.json() as Promise<T>
}

export async function sendChat(params: {
  messages: ChatMessageIn[]
  model: string
  petitionId: string | null
  settings: ChatSettings
}): Promise<ChatCompletionResponse> {
  return request<ChatCompletionResponse>('/v1/chat/completions', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      model: params.model,
      messages: params.messages,
      petition_id: params.petitionId,
      rag_top_k: params.settings.ragTopK,
      web_max_results: params.settings.webMaxResults,
      use_internet_on_recreate: params.settings.useInternetOnRecreate,
      persona_id: params.settings.personaId,
    }),
  })
}

export async function listPersonas(): Promise<PersonasListResponse> {
  return request<PersonasListResponse>('/v1/personas')
}

export async function uploadPetition(file: File): Promise<UploadResponse> {
  const form = new FormData()
  form.append('file', file)
  return request<UploadResponse>('/v1/uploads', {
    method: 'POST',
    body: form,
  })
}

export async function checkHealth(): Promise<{ status: string }> {
  return request('/health')
}

export async function listModels(): Promise<ModelsListResponse> {
  return request('/v1/models')
}

export async function getIndexStatus(): Promise<IndexStatusResponse> {
  return request('/v1/index')
}

export type ProgressEvent = {
  type: 'progress' | 'done' | 'error' | 'ping'
  percent?: number
  message?: string
  detail?: string
  result?: IndexRebuildResponse | ScrapeResponse
}

async function consumeNdjsonStream(
  path: string,
  onProgress: (percent: number, message: string) => void,
): Promise<ProgressEvent['result']> {
  const response = await fetch(`${API_BASE}${path}`, { method: 'POST' })
  if (!response.ok) {
    let detail = `Erro HTTP ${response.status}`
    try {
      const body = await response.json()
      detail = body.detail || detail
    } catch {
      /* ignore */
    }
    throw new Error(typeof detail === 'string' ? detail : JSON.stringify(detail))
  }
  if (!response.body) {
    throw new Error('Resposta sem corpo (stream indisponível).')
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  let finalResult: ProgressEvent['result']

  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    const lines = buffer.split('\n')
    buffer = lines.pop() ?? ''

    for (const line of lines) {
      const trimmed = line.trim()
      if (!trimmed) continue
      const event = JSON.parse(trimmed) as ProgressEvent
      if (event.type === 'progress' && typeof event.percent === 'number') {
        onProgress(event.percent, event.message || '')
      } else if (event.type === 'done') {
        finalResult = event.result
      } else if (event.type === 'error') {
        throw new Error(event.detail || 'Falha na operação.')
      }
    }
  }

  if (buffer.trim()) {
    const event = JSON.parse(buffer.trim()) as ProgressEvent
    if (event.type === 'done') finalResult = event.result
    if (event.type === 'error') {
      throw new Error(event.detail || 'Falha na operação.')
    }
  }

  return finalResult
}

export async function rebuildIndex(
  onProgress: (percent: number, message: string) => void,
): Promise<IndexRebuildResponse> {
  const result = await consumeNdjsonStream('/v1/index/rebuild/stream', onProgress)
  return result as IndexRebuildResponse
}

export async function scrapePetitions(
  onProgress: (percent: number, message: string) => void,
): Promise<ScrapeResponse> {
  const result = await consumeNdjsonStream('/v1/scrape/stream', onProgress)
  return result as ScrapeResponse
}

export async function submitHumanValidation(
  body: HumanValidationCreateRequest,
): Promise<HumanValidationPayload> {
  return request('/v1/validations', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
}

export async function listHumanValidations(): Promise<HumanValidationListResponse> {
  return request('/v1/validations')
}
