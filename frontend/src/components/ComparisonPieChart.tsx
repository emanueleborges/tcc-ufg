import { forwardRef } from 'react'

interface Props {
  humanMeanMinutes: number | null
  humanMeanLabel: string | null
  prototypeMeanSeconds: number
  prototypeMeanLabel: string
  speedupFactor: number | null
}

const SIZE = 280
const CX = SIZE / 2
const CY = SIZE / 2
const R = 96

function polar(cx: number, cy: number, r: number, angleDeg: number) {
  const rad = ((angleDeg - 90) * Math.PI) / 180
  return { x: cx + r * Math.cos(rad), y: cy + r * Math.sin(rad) }
}

function arcPath(
  cx: number,
  cy: number,
  r: number,
  startAngle: number,
  endAngle: number,
): string {
  const start = polar(cx, cy, r, endAngle)
  const end = polar(cx, cy, r, startAngle)
  const large = endAngle - startAngle > 180 ? 1 : 0
  return [
    `M ${cx} ${cy}`,
    `L ${end.x} ${end.y}`,
    `A ${r} ${r} 0 ${large} 1 ${start.x} ${start.y}`,
    'Z',
  ].join(' ')
}

export const ComparisonPieChart = forwardRef<SVGSVGElement, Props>(
  function ComparisonPieChart(
    {
      humanMeanMinutes,
      humanMeanLabel,
      prototypeMeanSeconds,
      prototypeMeanLabel,
      speedupFactor,
    },
    ref,
  ) {
    if (humanMeanMinutes == null || humanMeanMinutes <= 0) {
      return (
        <p className="dashboard-hint">
          Registre tempos humanos para gerar o gráfico de comparação.
        </p>
      )
    }

    const humanSeconds = humanMeanMinutes * 60
    const total = humanSeconds + prototypeMeanSeconds
    const humanPct = (humanSeconds / total) * 100
    const protoPct = (prototypeMeanSeconds / total) * 100
    // Fatia mínima visual para a aplicação (senão some no gráfico)
    const protoAngle = Math.max(2.5, (protoPct / 100) * 360)
    const humanAngle = 360 - protoAngle

    return (
      <div className="pie-wrap">
        <svg
          ref={ref}
          viewBox={`0 0 ${SIZE} ${SIZE}`}
          width={SIZE}
          height={SIZE}
          className="pie-chart"
          role="img"
          aria-label="Comparação de tempo médio: humano versus aplicação"
          xmlns="http://www.w3.org/2000/svg"
        >
          <rect width={SIZE} height={SIZE} fill="var(--assistant-bg, #1a2420)" />
          <path
            d={arcPath(CX, CY, R, 0, humanAngle)}
            className="pie-slice-human"
          />
          <path
            d={arcPath(CX, CY, R, humanAngle, 360)}
            className="pie-slice-proto"
          />
          <circle cx={CX} cy={CY} r={52} className="pie-hole" />
          <text x={CX} y={CY - 6} className="pie-center-value">
            {speedupFactor != null ? `${speedupFactor}×` : '—'}
          </text>
          <text x={CX} y={CY + 14} className="pie-center-label">
            mais rápido
          </text>
        </svg>

        <ul className="pie-legend">
          <li>
            <span className="pie-swatch pie-swatch-human" />
            <div>
              <strong>Avaliação humana</strong>
              <span>
                {humanMeanLabel} ({humanPct.toFixed(2)}%)
              </span>
            </div>
          </li>
          <li>
            <span className="pie-swatch pie-swatch-proto" />
            <div>
              <strong>Avaliação pela aplicação</strong>
              <span>
                {prototypeMeanLabel} ({protoPct.toFixed(2)}%)
              </span>
            </div>
          </li>
        </ul>
      </div>
    )
  },
)
