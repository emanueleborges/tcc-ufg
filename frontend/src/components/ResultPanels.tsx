import type {
  AnalysisPayload,
  PromptInjectionReport,
  RecreationPayload,
} from '../api/types'

function downloadText(filename: string, content: string, mime: string) {
  const blob = new Blob([content], { type: mime })
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = filename
  anchor.click()
  URL.revokeObjectURL(url)
}

const PRIMARY_SCORE_KEYS = [
  'estrutura',
  'clareza',
  'coerencia',
  'fundamentacao',
  'consistencia',
  'elementos_essenciais',
  'geral',
]

const RISK_LABEL: Record<PromptInjectionReport['risk'], string> = {
  none: 'Nenhum',
  low: 'Baixo',
  medium: 'Médio',
  high: 'Alto',
  critical: 'Crítico',
}

const VERDICT_LABEL: Record<NonNullable<PromptInjectionReport['verdict']>, string> = {
  clean: 'Limpo',
  suspicious: 'Suspeito',
  malicious: 'Prompt malicioso detectado',
}

interface AnalysisProps {
  analysis: AnalysisPayload
}

export function AnalysisPanel({ analysis }: AnalysisProps) {
  const scoreEntries = Object.entries(analysis.scores).filter(([name]) =>
    PRIMARY_SCORE_KEYS.includes(name),
  )
  const featureEntries = Object.entries(analysis.features).sort(([a], [b]) =>
    a.localeCompare(b),
  )
  const injection = analysis.prompt_injection

  return (
    <div className="result-panel">
      <h3>Painel de análise</h3>

      {injection && <InjectionSection report={injection} />}

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

function InjectionSection({ report }: { report: PromptInjectionReport }) {
  const riskClass = `injection-risk is-${report.risk}`
  const verdict = report.verdict ?? (report.risk === 'none' ? 'clean' : 'suspicious')
  return (
    <section className={`injection-panel ${riskClass}`}>
      <h4>Segurança — injeção de prompt (OWASP)</h4>
      <p className="injection-summary">
        Status:{' '}
        <strong>{VERDICT_LABEL[verdict] ?? verdict}</strong>
        {' · '}
        Risco: <strong>{RISK_LABEL[report.risk] ?? report.risk}</strong>
        {' · '}
        Score: <strong>{report.score}/100</strong>
        {report.blocked_for_llm ? ' · Recriação com LLM bloqueada' : ''}
      </p>
      <p className="injection-owasp">
        Framework:{' '}
        <strong>
          {report.owasp_id ?? 'LLM01:2025'} — {report.owasp_name ?? 'Prompt Injection'}
        </strong>
        {report.owasp_url && (
          <>
            {' '}
            (
            <a href={report.owasp_url} target="_blank" rel="noreferrer">
              OWASP GenAI
            </a>
            )
          </>
        )}
      </p>
      {report.attack_types && report.attack_types.length > 0 && (
        <p>
          <strong>Tipos:</strong> {report.attack_types.join(' · ')}
        </p>
      )}
      {report.techniques && report.techniques.length > 0 && (
        <p>
          <strong>Técnicas:</strong> {report.techniques.join(' · ')}
        </p>
      )}
      {report.objectives && report.objectives.length > 0 && (
        <p>
          <strong>Objetivos do ataque:</strong> {report.objectives.join(' · ')}
        </p>
      )}
      <p>{report.summary}</p>
      {report.findings.length > 0 && (
        <ul className="injection-findings">
          {report.findings.map((finding, index) => (
            <li key={`${finding.pattern_id}-${index}`}>
              <strong>[{finding.severity}]</strong> {finding.description}
              {finding.owasp_categories && finding.owasp_categories.length > 0 && (
                <>
                  <br />
                  <span className="injection-cats">
                    OWASP: {finding.owasp_categories.join(' · ')}
                  </span>
                </>
              )}
              <br />
              <code>{finding.matched || finding.excerpt}</code>
            </li>
          ))}
        </ul>
      )}
    </section>
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
