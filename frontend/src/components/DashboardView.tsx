import { useCallback, useEffect, useRef, useState } from 'react'
import {
  deleteReadingTime,
  listReadingTimes,
  measureAnalysisTimes,
  submitReadingTime,
  updateReadingTime,
} from '../api/client'
import type { ReadingTimeEntry, ReadingTimeListResponse } from '../api/types'
import { ReadingTimeChart } from './ReadingTimeChart'
import { ComparisonPieChart } from './ComparisonPieChart'
import {
  exportChartPng,
  exportReadingTimesCsv,
} from '../utils/exportReadingTimes'

const TIME_PATTERN = /^(\d{1,2}):([0-5]\d)$/

function parseTimeToMinutes(value: string): number | null {
  const match = TIME_PATTERN.exec(value.trim())
  if (!match) return null
  const minutes = Number(match[1]) * 60 + Number(match[2])
  return minutes >= 1 ? minutes : null
}

function minutesToLabel(minutes: number): string {
  return `${Math.floor(minutes / 60)}h${String(minutes % 60).padStart(2, '0')}`
}

/** Fallback só se a API ainda não tiver medições reais. */
const PROTOTYPE_MEAN_SECONDS = 1.3

function withPrototypeSummary(data: ReadingTimeListResponse): ReadingTimeListResponse {
  const meanMinutes = data.summary.mean_minutes
  const hasMeasured =
    (data.summary.prototype_measurements ?? 0) > 0 ||
    data.summary.prototype_source === 'measured'
  const protoSeconds =
    data.summary.prototype_mean_seconds ?? PROTOTYPE_MEAN_SECONDS
  const speedup =
    data.summary.speedup_factor ??
    (meanMinutes != null && protoSeconds > 0
      ? Math.round((meanMinutes * 60) / protoSeconds)
      : null)
  return {
    ...data,
    summary: {
      ...data.summary,
      prototype_mean_seconds: protoSeconds,
      prototype_mean_label:
        data.summary.prototype_mean_label ??
        `${protoSeconds.toFixed(1).replace('.', ',')} s`,
      prototype_measurements: data.summary.prototype_measurements ?? 0,
      prototype_source: hasMeasured
        ? 'measured'
        : (data.summary.prototype_source ?? 'fallback'),
      speedup_factor: speedup,
    },
  }
}

export function DashboardView() {
  const [data, setData] = useState<ReadingTimeListResponse | null>(null)
  const [lawyerName, setLawyerName] = useState('')
  const [timeInput, setTimeInput] = useState('')
  const [editingId, setEditingId] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [submitting, setSubmitting] = useState(false)
  const [measuring, setMeasuring] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [feedback, setFeedback] = useState<string | null>(null)
  const nameInputRef = useRef<HTMLInputElement>(null)
  const chartRef = useRef<SVGSVGElement>(null)
  const pieRef = useRef<SVGSVGElement>(null)

  const load = useCallback(async () => {
    try {
      setData(withPrototypeSummary(await listReadingTimes()))
      setError(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Falha ao carregar registros.')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

  function startEdit(item: ReadingTimeEntry) {
    setEditingId(item.entry_id)
    setLawyerName(item.lawyer_name)
    setTimeInput(
      `${String(Math.floor(item.minutes / 60)).padStart(2, '0')}:${String(
        item.minutes % 60,
      ).padStart(2, '0')}`,
    )
    setFeedback(null)
    requestAnimationFrame(() => {
      nameInputRef.current?.scrollIntoView({
        behavior: 'smooth',
        block: 'center',
      })
      nameInputRef.current?.focus()
      nameInputRef.current?.select()
    })
  }

  function cancelEdit() {
    setEditingId(null)
    setLawyerName('')
    setTimeInput('')
    setFeedback(null)
  }

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault()
    const minutes = parseTimeToMinutes(timeInput)
    if (minutes == null) {
      setFeedback('Informe o tempo no formato hh:mm (ex.: 01:45).')
      return
    }
    setSubmitting(true)
    setFeedback(null)
    try {
      if (editingId) {
        await updateReadingTime(editingId, {
          lawyerName: lawyerName.trim(),
          minutes,
        })
        cancelEdit()
        setFeedback('Registro atualizado.')
      } else {
        await submitReadingTime({ lawyerName: lawyerName.trim(), minutes })
        setLawyerName('')
        setTimeInput('')
        setFeedback('Registro salvo.')
      }
      await load()
    } catch (err) {
      setFeedback(err instanceof Error ? err.message : 'Falha ao salvar.')
    } finally {
      setSubmitting(false)
    }
  }

  async function handleDelete(item: ReadingTimeEntry) {
    if (!window.confirm(`Excluir o registro de ${item.lawyer_name}?`)) return
    try {
      await deleteReadingTime(item.entry_id)
      if (editingId === item.entry_id) cancelEdit()
      await load()
    } catch (err) {
      setFeedback(err instanceof Error ? err.message : 'Falha ao excluir.')
    }
  }

  async function handleExportCsv() {
    if (!data || data.items.length === 0) return
    exportReadingTimesCsv(data.items, {
      mean_label: data.summary.mean_label,
      prototype_mean_label: data.summary.prototype_mean_label ?? '1,3 s',
      speedup_factor: data.summary.speedup_factor ?? null,
    })
    setFeedback('CSV exportado.')
  }

  async function handleExportChart() {
    if (!chartRef.current) {
      setFeedback('Gráfico indisponível para exportar.')
      return
    }
    try {
      await exportChartPng(chartRef.current, 'grafico_tempos_leitura.png')
      setFeedback('Gráfico de linhas PNG exportado.')
    } catch (err) {
      setFeedback(err instanceof Error ? err.message : 'Falha ao exportar gráfico.')
    }
  }

  async function handleExportPie() {
    if (!pieRef.current) {
      setFeedback('Gráfico de pizza indisponível para exportar.')
      return
    }
    try {
      await exportChartPng(pieRef.current, 'grafico_pizza_humano_vs_app.png')
      setFeedback('Gráfico de pizza PNG exportado.')
    } catch (err) {
      setFeedback(err instanceof Error ? err.message : 'Falha ao exportar pizza.')
    }
  }

  async function handleMeasureApp() {
    setMeasuring(true)
    setFeedback(null)
    try {
      const result = await measureAnalysisTimes({ runs: 3 })
      setFeedback(
        `Tempo real medido: ${result.mean_label} (${result.runs} execuções em ${result.petition_name}).`,
      )
      await load()
    } catch (err) {
      setFeedback(
        err instanceof Error ? err.message : 'Falha ao medir tempo da aplicação.',
      )
    } finally {
      setMeasuring(false)
    }
  }

  return (
    <div className="dashboard">
      {loading && <p className="dashboard-hint">Carregando registros…</p>}
      {error && <div className="error-banner">{error}</div>}

      {data && (
        <>
          <section className="dashboard-section">
            <h3 className="dashboard-section-title">
              {editingId ? 'Editar registro' : 'Registrar tempo de leitura'}
            </h3>
            <form className="reading-form" onSubmit={handleSubmit}>
              <label className="validation-field">
                Nome do advogado *
                <input
                  ref={nameInputRef}
                  type="text"
                  value={lawyerName}
                  onChange={(e) => setLawyerName(e.target.value)}
                  placeholder="Nome do advogado"
                  required
                />
              </label>
              <label className="validation-field reading-time-field">
                Tempo de leitura (hh:mm) *
                <input
                  type="text"
                  inputMode="numeric"
                  value={timeInput}
                  onChange={(e) => setTimeInput(e.target.value)}
                  placeholder="ex.: 01:45"
                  required
                />
              </label>
              <div className="validation-actions">
                <button
                  type="submit"
                  className="primary-btn"
                  disabled={submitting || !lawyerName.trim() || !timeInput.trim()}
                >
                  {submitting
                    ? 'Salvando…'
                    : editingId
                      ? 'Salvar edição'
                      : 'Registrar'}
                </button>
                {editingId && (
                  <button
                    type="button"
                    className="link-btn"
                    onClick={cancelEdit}
                  >
                    Cancelar
                  </button>
                )}
                {feedback && (
                  <span className="validation-feedback">{feedback}</span>
                )}
              </div>
            </form>
          </section>

          <div className="dashboard-cards">
            <div className="dashboard-card">
              <span className="dashboard-card-value">
                {data.summary.mean_label ?? '—'}
              </span>
              <span className="dashboard-card-label">
                Tempo médio humano
              </span>
              <span className="dashboard-card-meta">
                {data.summary.count}{' '}
                {data.summary.count === 1 ? 'registro' : 'registros'}
              </span>
            </div>
            <div className="dashboard-card">
              <span className="dashboard-card-value">
                {data.summary.prototype_mean_label ?? '1,3 s'}
              </span>
              <span className="dashboard-card-label">
                Tempo médio da aplicação
              </span>
              <span className="dashboard-card-meta">
                {data.summary.prototype_source === 'measured'
                  ? `média de ${data.summary.prototype_measurements ?? 0} medições na base`
                  : 'ainda sem medições — use o botão abaixo'}
              </span>
            </div>
            <div className="dashboard-card">
              <span className="dashboard-card-value">
                {data.summary.speedup_factor != null
                  ? `${data.summary.speedup_factor}×`
                  : '—'}
              </span>
              <span className="dashboard-card-label">
                Ganho de velocidade
              </span>
              <span className="dashboard-card-meta">
                humano ÷ aplicação
              </span>
            </div>
          </div>

          <section className="dashboard-section">
            <div className="dashboard-section-header">
              <h3 className="dashboard-section-title">
                Tempo de leitura por advogado
              </h3>
              <div className="export-actions">
                <button
                  type="button"
                  className="new-chat-btn export-btn"
                  disabled={data.items.length === 0}
                  onClick={handleExportCsv}
                >
                  Exportar CSV
                </button>
                <button
                  type="button"
                  className="new-chat-btn export-btn"
                  disabled={data.items.length === 0}
                  onClick={handleExportChart}
                >
                  Exportar gráfico (PNG)
                </button>
              </div>
            </div>
            <ReadingTimeChart
              ref={chartRef}
              items={data.items}
              meanMinutes={data.summary.mean_minutes}
              prototypeMeanSeconds={
                data.summary.prototype_mean_seconds ?? PROTOTYPE_MEAN_SECONDS
              }
              prototypeMeanLabel={
                data.summary.prototype_mean_label ?? '1,3 s'
              }
            />
          </section>

          <section className="dashboard-section">
            <div className="dashboard-section-header">
              <h3 className="dashboard-section-title">
                Comparação humano × aplicação
              </h3>
              <div className="export-actions">
                <button
                  type="button"
                  className="primary-btn export-btn"
                  disabled={measuring}
                  onClick={handleMeasureApp}
                >
                  {measuring ? 'Medindo…' : 'Medir tempo da aplicação'}
                </button>
                <button
                  type="button"
                  className="new-chat-btn export-btn"
                  disabled={data.summary.mean_minutes == null}
                  onClick={handleExportPie}
                >
                  Exportar pizza (PNG)
                </button>
              </div>
            </div>
            <ComparisonPieChart
              ref={pieRef}
              humanMeanMinutes={data.summary.mean_minutes}
              humanMeanLabel={data.summary.mean_label}
              prototypeMeanSeconds={
                data.summary.prototype_mean_seconds ?? PROTOTYPE_MEAN_SECONDS
              }
              prototypeMeanLabel={
                data.summary.prototype_mean_label ?? '1,3 s'
              }
              speedupFactor={data.summary.speedup_factor ?? null}
            />
          </section>

          <section className="dashboard-section">
            <div className="dashboard-section-header">
              <h3 className="dashboard-section-title">Registros</h3>
              <button
                type="button"
                className="new-chat-btn export-btn"
                disabled={data.items.length === 0}
                onClick={handleExportCsv}
              >
                Exportar CSV
              </button>
            </div>
            {data.items.length > 0 ? (
              <ul className="dashboard-list">
                {data.items.map((item) => (
                  <li key={item.entry_id} className="dashboard-list-item">
                    <div className="dashboard-list-main">
                      <strong>{item.lawyer_name}</strong>
                      <span className="dashboard-list-meta">
                        {new Date(item.created_at).toLocaleDateString('pt-BR')}
                      </span>
                    </div>
                    <div className="dashboard-list-metrics">
                      <span>{item.label || minutesToLabel(item.minutes)}</span>
                      <button
                        type="button"
                        className="link-btn"
                        onClick={() => startEdit(item)}
                      >
                        Editar
                      </button>
                      <button
                        type="button"
                        className="link-btn danger-btn"
                        onClick={() => handleDelete(item)}
                      >
                        Excluir
                      </button>
                    </div>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="dashboard-hint">Nenhum registro ainda.</p>
            )}
          </section>
        </>
      )}
    </div>
  )
}
