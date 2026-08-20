import { forwardRef } from 'react'
import type { ReadingTimeEntry } from '../api/types'

interface Props {
  items: ReadingTimeEntry[]
  meanMinutes: number | null
  prototypeMeanSeconds: number
  prototypeMeanLabel: string
}

const WIDTH = 760
const HEIGHT = 280
const PAD = { top: 28, right: 20, bottom: 36, left: 52 }

function label(minutes: number): string {
  return `${Math.floor(minutes / 60)}h${String(minutes % 60).padStart(2, '0')}`
}

export const ReadingTimeChart = forwardRef<SVGSVGElement, Props>(
  function ReadingTimeChart(
    { items, meanMinutes, prototypeMeanSeconds, prototypeMeanLabel },
    ref,
  ) {
    const points = [...items].reverse()
    if (points.length === 0) return null

    const minutes = points.map((p) => p.minutes)
    const prototypeMinutes = prototypeMeanSeconds / 60
    const minY = 0
    const maxY = Math.max(...minutes, meanMinutes ?? 0) + 15
    const innerW = WIDTH - PAD.left - PAD.right
    const innerH = HEIGHT - PAD.top - PAD.bottom
    const xStep = points.length > 1 ? innerW / (points.length - 1) : 0

    const x = (i: number) => PAD.left + i * xStep
    const y = (m: number) =>
      PAD.top + innerH - ((m - minY) / (maxY - minY || 1)) * innerH

    const line = points.map((p, i) => `${x(i)},${y(p.minutes)}`).join(' ')
    const tickEvery = Math.max(1, Math.ceil(points.length / 10))
    const yTicks = [0, Math.round(maxY / 2), Math.round(maxY)]

    return (
      <div className="chart-wrap">
        <svg
          ref={ref}
          viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
          width={WIDTH}
          height={HEIGHT}
          className="reading-chart"
          role="img"
          aria-label="Gráfico de linhas dos tempos de leitura por advogado"
          xmlns="http://www.w3.org/2000/svg"
        >
          <rect width={WIDTH} height={HEIGHT} fill="var(--assistant-bg, #1a2420)" />

          {yTicks.map((tick) => (
            <g key={tick}>
              <line
                x1={PAD.left}
                x2={WIDTH - PAD.right}
                y1={y(tick)}
                y2={y(tick)}
                className="chart-grid"
              />
              <text x={PAD.left - 8} y={y(tick) + 4} className="chart-y-label">
                {label(tick)}
              </text>
            </g>
          ))}

          {meanMinutes != null && (
            <g>
              <line
                x1={PAD.left}
                x2={WIDTH - PAD.right}
                y1={y(meanMinutes)}
                y2={y(meanMinutes)}
                className="chart-mean-line"
              />
              <text
                x={WIDTH - PAD.right}
                y={y(meanMinutes) - 6}
                className="chart-mean-label"
              >
                média humana {label(meanMinutes)}
              </text>
            </g>
          )}

          <line
            x1={PAD.left}
            x2={WIDTH - PAD.right}
            y1={y(prototypeMinutes)}
            y2={y(prototypeMinutes)}
            className="chart-proto-line"
          />
          <text
            x={PAD.left + 4}
            y={y(prototypeMinutes) - 6}
            className="chart-proto-label"
          >
            média app {prototypeMeanLabel}
          </text>

          <polyline points={line} className="chart-line" />

          {points.map((p, i) => (
            <circle
              key={p.entry_id}
              cx={x(i)}
              cy={y(p.minutes)}
              r={4}
              className="chart-point"
            >
              <title>
                {p.lawyer_name} — {label(p.minutes)}
              </title>
            </circle>
          ))}

          {points.map((p, i) =>
            i % tickEvery === 0 || i === points.length - 1 ? (
              <text
                key={`x-${p.entry_id}`}
                x={x(i)}
                y={HEIGHT - PAD.bottom + 18}
                className="chart-x-label"
              >
                {i + 1}
              </text>
            ) : null,
          )}
        </svg>
        <div className="chart-legend">
          <span className="legend-item legend-human">média humana</span>
          <span className="legend-item legend-proto">média da aplicação</span>
          <span className="legend-item legend-series">tempos por advogado</span>
        </div>
      </div>
    )
  },
)
