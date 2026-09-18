interface ScoreCriterion {
  label: string
  application: number | null
  human: number | null
}

interface Props {
  criteria: ScoreCriterion[]
  acceptancePercent: number | null
  evaluatorCount: number
}

const WIDTH = 760
const HEIGHT = 330
const PAD = { top: 38, right: 20, bottom: 58, left: 42 }

export function ScoreComparisonChart({
  criteria,
  acceptancePercent,
  evaluatorCount,
}: Props) {
  const innerWidth = WIDTH - PAD.left - PAD.right
  const innerHeight = HEIGHT - PAD.top - PAD.bottom
  const groupWidth = innerWidth / Math.max(criteria.length, 1)
  const barWidth = Math.min(28, groupWidth * 0.3)
  const y = (scorePercent: number) =>
    PAD.top + innerHeight - (Math.max(0, Math.min(100, scorePercent)) / 100) * innerHeight

  return (
    <div className="score-result-layout">
      <div className="score-chart-wrap">
        <svg
          viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
          className="score-comparison-chart"
          role="img"
          aria-label="Comparativo de notas da aplicação e da avaliação humana"
        >
          <text x={PAD.left} y={22} className="score-chart-title">
            Comparativo de notas (0–10)
          </text>

          {[0, 50, 100].map((tick) => (
            <g key={tick}>
              <line
                x1={PAD.left}
                x2={WIDTH - PAD.right}
                y1={y(tick)}
                y2={y(tick)}
                className="score-chart-grid"
              />
              <text
                x={PAD.left - 9}
                y={y(tick) + 4}
                className="score-chart-axis-label"
              >
                {tick / 10}
              </text>
            </g>
          ))}

          {criteria.map((criterion, index) => {
            const center = PAD.left + groupWidth * index + groupWidth / 2
            const applicationHeight =
              criterion.application == null
                ? 0
                : PAD.top + innerHeight - y(criterion.application)
            const humanHeight =
              criterion.human == null ? 0 : PAD.top + innerHeight - y(criterion.human)

            return (
              <g key={criterion.label}>
                {criterion.application != null && (
                  <rect
                    x={center - barWidth - 2}
                    y={y(criterion.application)}
                    width={barWidth}
                    height={applicationHeight}
                    rx={3}
                    className="score-bar score-bar--app"
                  >
                    <title>
                      {criterion.label} — Aplicação:{' '}
                      {(criterion.application / 10).toFixed(1)}
                    </title>
                  </rect>
                )}
                {criterion.human != null && (
                  <rect
                    x={center + 2}
                    y={y(criterion.human)}
                    width={barWidth}
                    height={humanHeight}
                    rx={3}
                    className="score-bar score-bar--human"
                  >
                    <title>
                      {criterion.label} — Avaliação humana:{' '}
                      {(criterion.human / 10).toFixed(1)}
                    </title>
                  </rect>
                )}
                <text
                  x={center}
                  y={HEIGHT - PAD.bottom + 20}
                  className="score-chart-category"
                >
                  {criterion.label}
                </text>
              </g>
            )
          })}
        </svg>
        <div className="score-chart-legend" aria-label="Legenda">
          <span className="score-legend-item score-legend-item--app">
            Aplicação
          </span>
          <span className="score-legend-item score-legend-item--human">
            Avaliação humana
          </span>
        </div>
      </div>

      {acceptancePercent != null && (
        <aside className="acceptance-result-card">
          <span>Utilizaria esta aplicação</span>
          <strong>{acceptancePercent}%</strong>
          <b>dos avaliadores disseram SIM</b>
          <small>
            Com base em {evaluatorCount}{' '}
            {evaluatorCount === 1 ? 'registro' : 'registros'}
          </small>
        </aside>
      )}
    </div>
  )
}
