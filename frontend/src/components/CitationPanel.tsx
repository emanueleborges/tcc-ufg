import type { Citation } from '../api/types'

interface Props {
  citations: Citation[]
  sourceId?: string
}

export function CitationPanel({ citations }: Props) {
  if (!citations.length) return null

  return (
    <details className="citations">
      <summary>
        Referências ({citations.length})
      </summary>
      <ul>
        {citations.map((c, i) => (
          <li key={`${c.title}-${i}`}>
            {c.url ? (
              <a href={c.url} target="_blank" rel="noreferrer">
                {i + 1}. {c.title || c.url}
              </a>
            ) : (
              <strong>
                {i + 1}. {c.title}
              </strong>
            )}
            {c.detail && <p>{c.detail}</p>}
          </li>
        ))}
      </ul>
    </details>
  )
}
