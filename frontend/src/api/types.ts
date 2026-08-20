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
  persona?: PersonaOut | null
  citations: Citation[]
  analysis?: AnalysisPayload | null
}

export interface PromptInjectionFinding {
  pattern_id: string
  severity: string
  description: string
  excerpt: string
  matched?: string
  owasp_categories?: string[]
}

export interface PromptInjectionReport {
  risk: 'none' | 'low' | 'medium' | 'high' | 'critical'
  score: number
  summary: string
  findings: PromptInjectionFinding[]
  scanned_chars: number
  owasp_id?: string
  owasp_name?: string
  owasp_url?: string
  attack_types?: string[]
  techniques?: string[]
  objectives?: string[]
  verdict?: 'clean' | 'suspicious' | 'malicious'
}

export interface AnalysisPayload {
  scores: Record<string, number>
  problems: string[]
  suggestions: string[]
  features: Record<string, string | number | boolean>
  markdown: string
  prompt_injection?: PromptInjectionReport | null
}

export type ProblemVerdict = 'confirmed' | 'partial' | 'rejected'

export interface ProblemAssessment {
  problem: string
  verdict: ProblemVerdict
  note?: string
}

export interface ComparisonMetrics {
  mae_scores: number
  agreement_rate: number
  dimension_gaps: Record<string, number>
  problems_confirmed: number
  problems_partial: number
  problems_rejected: number
  summary: string
}

export interface HumanValidationPayload {
  validation_id: string
  petition_id: string
  petition_name: string
  reviewer_name: string
  created_at: string
  prototype_scores: Record<string, number>
  human_scores: Record<string, number>
  problem_assessments: ProblemAssessment[]
  documentation_ok: boolean
  textual_cohesion_ok: boolean
  argumentative_consistency_ok: boolean
  legal_basis_ok: boolean
  final_quality: number
  comments: string
  comparison: ComparisonMetrics
  markdown_report: string
}

export interface HumanValidationCreateRequest {
  petition_id: string
  petition_name: string
  reviewer_name: string
  prototype_scores: Record<string, number>
  human_scores: Record<string, number>
  problem_assessments: ProblemAssessment[]
  documentation_ok: boolean
  textual_cohesion_ok: boolean
  argumentative_consistency_ok: boolean
  legal_basis_ok: boolean
  final_quality: number
  comments: string
}

export interface HumanValidationListResponse {
  items: HumanValidationPayload[]
  summary: {
    count: number
    mean_mae: number | null
    mean_agreement_rate: number | null
    mean_final_quality: number | null
  }
}

export interface DimensionMetric {
  name: string
  label: string
  mean_prototype: number
  mean_human: number
  mean_gap: number
}

export interface ProblemVerdicts {
  confirmed: number
  partial: number
  rejected: number
  total: number
}

export interface ValidationMetricsResponse {
  count: number
  petitions: number
  reviewers: number
  mean_mae: number | null
  mean_agreement_rate: number | null
  mean_final_quality: number | null
  dimensions: DimensionMetric[]
  problems: ProblemVerdicts
}

export interface ReadingTimeEntry {
  entry_id: string
  lawyer_name: string
  minutes: number
  label: string
  created_at: string
}

export interface ReadingTimeListResponse {
  items: ReadingTimeEntry[]
  summary: {
    count: number
    mean_minutes: number | null
    mean_label: string | null
    prototype_mean_seconds?: number
    prototype_mean_label?: string
    prototype_measurements?: number
    prototype_source?: 'measured' | 'fallback' | string
    speedup_factor?: number | null
  }
}

export interface AnalysisTimeEntry {
  entry_id: string
  petition_name: string
  seconds: number
  label: string
  created_at: string
  source: string
}

export interface MeasureAnalysisTimeResponse {
  petition_name: string
  runs: number
  mean_seconds: number
  mean_label: string
  items: AnalysisTimeEntry[]
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
  new_accepted?: number
  new_rejected?: number
  new_partial?: number
  candidates_found?: number
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

export interface PersonaOut {
  id: string
  label: string
  description: string
}

export interface PersonasListResponse {
  default_id: string
  data: PersonaOut[]
}

export interface ChatSettings {
  ragTopK: number
  webMaxResults: number
  personaId: string
}

export interface UiMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  source?: SourceInfo
  routing?: RoutingInfo
  persona?: PersonaOut | null
  citations?: Citation[]
  model?: string
  attachmentName?: string
  analysis?: AnalysisPayload | null
}
