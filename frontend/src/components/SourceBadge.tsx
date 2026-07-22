import type { SourceInfo } from '../api/types'

const SOURCE_CLASS: Record<string, string> = {
  rag: 'badge-rag',
  ollama: 'badge-ollama',
  internet: 'badge-internet',
  petition_analysis: 'badge-analysis',
  petition_recreation: 'badge-recreation',
  system: 'badge-system',
}

interface Props {
  source: SourceInfo
  model?: string
  routingMode?: string
}

export function SourceBadge({ source, model, routingMode }: Props) {
  const cls = SOURCE_CLASS[source.id] ?? 'badge-system'
  return (
    <div className={`source-badge ${cls}`}>
      <span>
        {source.icon} Fonte: <strong>{source.label}</strong>
      </span>
      {model && source.id !== 'system' && (
        <span className="badge-meta">Modelo: {model}</span>
      )}
      {routingMode && (
        <span className="badge-meta">Roteamento: {routingMode}</span>
      )}
    </div>
  )
}
