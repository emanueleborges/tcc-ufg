export type ChatRole = 'user' | 'assistant' | 'system'

export interface ChatMessageIn {
  role: ChatRole
  content: string
}

export interface Citation {
  title: string
  detail: string
  url: string
}

export interface SourceInfo {
  id: string
  label: string
  icon: string
}

export interface RoutingInfo {
  intent: string
  mode: string
  reason: string
}

export interface ChatCompletionResponse {
  id: string
  object: string
  created: number
  model: string
  choices: Array<{
    index: number
    message: { role: 'assistant'; content: string }
    finish_reason: string
  }>
  source: SourceInfo
  routing: RoutingInfo
  citations: Citation[]
  analysis?: AnalysisPayload | null
  recreation?: RecreationPayload | null
}

export interface AnalysisPayload {
  scores: Record<string, number>
  problems: string[]
  suggestions: string[]
  features: Record<string, string | number | boolean>
  markdown: string
}

export interface RecreationPayload {
  markdown: string
  warnings: string[]
  used_ollama: boolean
}

export interface UploadResponse {
  petition_id: string
  file_name: string
  path: string
  size_bytes: number
  uploaded_at: string
}

export interface IndexStatusResponse {
  exists: boolean
  index_dir: string
  documents: number | null
  chunks: number | null
}

export interface IndexRebuildResponse {
  documents: number
  chunks: number
  report_path: string
  index_dir: string
}

export interface ScrapeResponse {
  total_documents: number
  message: string
}

export interface ModelOut {
  id: string
  object: string
  owned_by: string
  description: string
}

export interface ModelsListResponse {
  object: string
  data: ModelOut[]
}

export interface ChatSettings {
  ragTopK: number
  webMaxResults: number
  useInternetOnRecreate: boolean
}

export interface UiMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  source?: SourceInfo
  routing?: RoutingInfo
  citations?: Citation[]
  model?: string
  attachmentName?: string
  analysis?: AnalysisPayload | null
  recreation?: RecreationPayload | null
}
