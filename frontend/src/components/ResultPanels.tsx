import type { AnalysisPayload, RecreationPayload } from '../api/types'

function downloadText(filename: string, content: string, mime: string) {
  const blob = new Blob([content], { type: mime })
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = filename
  anchor.click()
  URL.revokeObjectURL(url)
}

interface AnalysisProps {
  analysis: AnalysisPayload
}

export function AnalysisPanel({ analysis }: AnalysisProps) {
  const scoreEntries = Object.entries(analysis.scores)
  const featureEntries = Object.entries(analysis.features).sort(([a], [b]) =>
    a.localeCompare(b),
  )

  return (
    <div className="result-panel">
      <h3>Painel de análise</h3>

      {scoreEntries.length > 0 && (
        <div className="score-grid">
          {scoreEntries.map(([name, score]) => (
            <div key={name} className="score-card">
              <span>{name}</span>
              <strong>{score}/10</strong>
            </div>
          ))}
        </div>
      )}

      <h4>Pontos de melhoria</h4>
      {analysis.problems.length > 0 ? (
        <ul className="warn-list">
          {analysis.problems.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      ) : (
        <p className="ok-text">Nenhum problema estrutural grave detectado.</p>
      )}

      <h4>Sugestões</h4>
      <ul>
        {analysis.suggestions.map((item) => (
          <li key={item}>{item}</li>
        ))}
      </ul>

      {featureEntries.length > 0 && (
        <details>
          <summary>Features jurídicas ({featureEntries.length})</summary>
          <table className="feature-table">
            <thead>
              <tr>
                <th>Feature</th>
                <th>Valor</th>
              </tr>
            </thead>
            <tbody>
              {featureEntries.map(([key, value]) => (
                <tr key={key}>
                  <td>{key}</td>
                  <td>{String(value)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </details>
      )}

      {analysis.markdown && (
        <button
          type="button"
          className="panel-download"
          onClick={() =>
            downloadText(
              'relatorio_critico.md',
              analysis.markdown,
              'text/markdown;charset=utf-8',
            )
          }
        >
          Baixar relatório Markdown
        </button>
      )}
    </div>
  )
}

interface RecreationProps {
  recreation: RecreationPayload
}

export function RecreationPanel({ recreation }: RecreationProps) {
  return (
    <div className="result-panel">
      <h3>Petição recriada</h3>
      {recreation.used_ollama && (
        <p className="ok-text">Comentários gerados com Ollama.</p>
      )}
      {recreation.warnings.map((warning) => (
        <p key={warning} className="warn-text">
          {warning}
        </p>
      ))}
      {recreation.markdown && (
        <button
          type="button"
          className="panel-download"
          onClick={() =>
            downloadText(
              'peticao_recriada.md',
              recreation.markdown,
              'text/markdown;charset=utf-8',
            )
          }
        >
          Baixar petição recriada (Markdown)
        </button>
      )}
      <details>
        <summary>Ver markdown completo</summary>
        <pre className="markdown-preview">{recreation.markdown}</pre>
      </details>
    </div>
  )
}
