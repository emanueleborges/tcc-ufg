import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  listReadingTimes,
  listHumanValidations,
  listApplicationEvaluations,
  listEvaluators,
  deleteAnalyzedPetition,
  deleteHumanValidation,
  submitHumanValidation,
  submitReadingTime,
  updateReadingTime,
  updateHumanValidation,
} from '../api/client'
import type {
  ApplicationEvaluationEntry,
  ApplicationEvaluationListResponse,
  EvaluatorOut,
  HumanValidationPayload,
  ProblemAssessment,
  ReadingTimeEntry,
  ReadingTimeListResponse,
} from '../api/types'
import { ComparisonPieChart } from './ComparisonPieChart'
import {
  exportChartPng,
} from '../utils/exportReadingTimes'
import { ReadingTimeChart } from './ReadingTimeChart'
import { ScoreComparisonChart } from './ScoreComparisonChart'

const TIME_PATTERN = /^(\d{1,2}):([0-5]\d)$/

/** Formata dígitos digitados para hh:mm (ex.: 0830 → 08:30). */
function formatTimeDigits(raw: string): string {
  const digits = raw.replace(/\D/g, '').slice(0, 4)
  if (digits.length === 0) return ''
  if (digits.length <= 2) return digits
  return `${digits.slice(0, 2)}:${digits.slice(2)}`
}

/** Completa com zeros à esquerda (ex.: 830 → 08:30, 8:3 → 08:03). */
function finalizeTimeInput(value: string): string {
  const digits = value.replace(/\D/g, '').slice(0, 4)
  if (digits.length === 0) return ''

  let hours: number
  let mins: number
  if (digits.length <= 2) {
    hours = Number(digits)
    mins = 0
  } else if (digits.length === 3) {
    const asHourMinute = Number(digits.slice(1))
    if (asHourMinute <= 59) {
      hours = Number(digits[0])
      mins = asHourMinute
    } else {
      hours = Number(digits.slice(0, 2))
      mins = Number(digits[2])
    }
  } else {
    hours = Number(digits.slice(0, 2))
    mins = Number(digits.slice(2))
  }

  if (!Number.isFinite(hours) || !Number.isFinite(mins) || hours < 0 || mins < 0 || mins > 59) {
    return formatTimeDigits(value)
  }
  return `${String(hours).padStart(2, '0')}:${String(mins).padStart(2, '0')}`
}

function parseTimeToMinutes(value: string): number | null {
  const normalized = finalizeTimeInput(value)
  const match = TIME_PATTERN.exec(normalized)
  if (!match) return null
  const minutes = Number(match[1]) * 60 + Number(match[2])
  return minutes >= 1 ? minutes : null
}

/** Fallback só se a API ainda não tiver medições reais. */
const PROTOTYPE_MEAN_SECONDS = 1.3
const PAGE_SIZE = 10
const SCORE_FIELDS = [
  ['estrutura', 'Estrutura'],
  ['clareza', 'Clareza'],
  ['coerencia', 'Coerência'],
  ['fundamentacao', 'Fundamentação'],
  ['consistencia', 'Consistência'],
  ['elementos_essenciais', 'Elementos essenciais'],
] as const

const SCORE_CHART_LABELS = {
  estrutura: 'Estrutura',
  clareza: 'Clareza',
  coerencia: 'Coerência',
  fundamentacao: 'Fundam.',
  consistencia: 'Consist.',
  elementos_essenciais: 'Elementos',
} satisfies Record<(typeof SCORE_FIELDS)[number][0], string>

interface DashboardProps {
  petitionId?: string | null
  petitionName?: string | null
  prototypeScores?: Record<string, number> | null
  prototypeProblems?: string[]
}

type PendingProblemAssessment = Omit<ProblemAssessment, 'verdict'> & {
  verdict: ProblemAssessment['verdict'] | ''
}

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

function minutesToLabel(minutes: number): string {
  return `${Math.floor(minutes / 60)}h${String(minutes % 60).padStart(2, '0')}`
}

function minutesToTimeInput(minutes: number): string {
  return `${String(Math.floor(minutes / 60)).padStart(2, '0')}:${String(
    minutes % 60,
  ).padStart(2, '0')}`
}

function toPercentDisplay(value: number | null | undefined): string {
  if (value == null || Number.isNaN(Number(value))) return ''
  const num = Number(value)
  const pct = num <= 10 ? num * 10 : num
  return String(Math.round(pct))
}

function parsePercent(value: string): number | null {
  const normalized = value.trim().replace(/%/g, '').replace(',', '.')
  const score = Number(normalized)
  return normalized !== '' && Number.isFinite(score) && score >= 0 && score <= 100
    ? Math.round(score)
    : null
}

function percentInputValue(value: string): string {
  return value.trim() ? `${value.replace(/%/g, '')}%` : ''
}

function onPercentInputChange(raw: string, setter: (next: string) => void) {
  const digits = raw.replace(/[^\d]/g, '')
  if (digits === '') {
    setter('')
    return
  }
  const clipped = Math.min(100, Number(digits))
  setter(String(Number.isFinite(clipped) ? clipped : ''))
}

function average(values: number[]): number | null {
  if (values.length === 0) return null
  return Math.round(values.reduce((sum, value) => sum + value, 0) / values.length)
}

function paginate<T>(items: T[], page: number, pageSize = PAGE_SIZE): T[] {
  const start = Math.max(0, page) * pageSize
  return items.slice(start, start + pageSize)
}

function totalPages(count: number, pageSize = PAGE_SIZE): number {
  return Math.max(1, Math.ceil(count / pageSize))
}

function yesNoFromScore(score: number | null | undefined): 'sim' | 'nao' | '' {
  if (score == null || Number.isNaN(Number(score))) return ''
  return Number(score) >= 50 ? 'sim' : 'nao'
}

function yesNoLabel(score: number | null | undefined): string {
  const answer = yesNoFromScore(score)
  if (answer === 'sim') return 'SIM'
  if (answer === 'nao') return 'NÃO'
  return '—'
}

function scoreFromYesNo(answer: 'sim' | 'nao' | ''): number | null {
  if (answer === 'sim') return 100
  if (answer === 'nao') return 0
  return null
}

function shortPetitionLabel(entry: ApplicationEvaluationEntry): string {
  const name = entry.petition_name || entry.petition_id || 'Petição'
  return name.length > 72 ? `${name.slice(0, 69)}…` : name
}

export function DashboardView({
  petitionId: activePetitionId,
  prototypeScores: activePrototypeScores,
  prototypeProblems = [],
}: DashboardProps) {
  const [data, setData] = useState<ReadingTimeListResponse | null>(null)
  const [validations, setValidations] = useState<HumanValidationPayload[]>([])
  const [appEvaluations, setAppEvaluations] =
    useState<ApplicationEvaluationListResponse | null>(null)
  const [evaluators, setEvaluators] = useState<EvaluatorOut[]>([])
  const [allEvaluators, setAllEvaluators] = useState<EvaluatorOut[]>([])
  const [selectedPetitionId, setSelectedPetitionId] = useState('')
  const [evaluatorId, setEvaluatorId] = useState('')
  const [timeEvaluatorId, setTimeEvaluatorId] = useState('')
  const [timeInput, setTimeInput] = useState('')
  const [editingTimeEntryId, setEditingTimeEntryId] = useState<string | null>(null)
  const [humanScores, setHumanScores] = useState<Record<string, string>>({})
  const [generalScore, setGeneralScore] = useState('')
  const [applicationUseAnswer, setApplicationUseAnswer] = useState<'sim' | 'nao' | ''>('')
  const [problemAssessments, setProblemAssessments] = useState<PendingProblemAssessment[]>([])
  const [documentationOk, setDocumentationOk] = useState(false)
  const [textualCohesionOk, setTextualCohesionOk] = useState(false)
  const [argumentativeConsistencyOk, setArgumentativeConsistencyOk] = useState(false)
  const [legalBasisOk, setLegalBasisOk] = useState(false)
  const [editingValidationId, setEditingValidationId] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [submitting, setSubmitting] = useState(false)
  const [submittingTime, setSubmittingTime] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [feedback, setFeedback] = useState<string | null>(null)
  const [timeFeedback, setTimeFeedback] = useState<string | null>(null)
  const [validationsPage, setValidationsPage] = useState(0)
  const [timesPage, setTimesPage] = useState(0)
  const evaluatorSelectRef = useRef<HTMLSelectElement>(null)
  const pieRef = useRef<SVGSVGElement>(null)
  const chartRef = useRef<SVGSVGElement>(null)

  const selectedSnapshot = useMemo(() => {
    if (!selectedPetitionId || !appEvaluations) return null
    return (
      appEvaluations.items.find((item) => item.petition_id === selectedPetitionId) ??
      null
    )
  }, [appEvaluations, selectedPetitionId])

  const campaign = selectedSnapshot?.campaign ?? null
  const requiredEvaluations =
    campaign?.required ?? appEvaluations?.summary.required_evaluations ?? 30
  const campaignComplete = Boolean(campaign?.is_complete)

  const load = useCallback(async (petitionId?: string) => {
    try {
      const apps = await listApplicationEvaluations()
      setAppEvaluations(apps)
      setData(withPrototypeSummary(await listReadingTimes()))
      setAllEvaluators((await listEvaluators()).items)

      const linked = apps.items.filter((item) => item.petition_id)
      let nextPetition: string
      if (petitionId !== undefined) {
        // '' = escolher a primeira restante (após exclusão)
        nextPetition =
          petitionId && linked.some((item) => item.petition_id === petitionId)
            ? petitionId
            : linked[0]?.petition_id || ''
      } else {
        const preferred =
          selectedPetitionId || activePetitionId || linked[0]?.petition_id || ''
        nextPetition =
          preferred && linked.some((item) => item.petition_id === preferred)
            ? preferred
            : linked[0]?.petition_id || ''
      }
      if (nextPetition) {
        setSelectedPetitionId(nextPetition)
        setValidations((await listHumanValidations(nextPetition)).items)
        setEvaluators((await listEvaluators(nextPetition)).items)
      } else {
        setSelectedPetitionId('')
        setValidations([])
        setEvaluators((await listEvaluators()).items)
      }
      setError(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Falha ao carregar registros.')
    } finally {
      setLoading(false)
    }
  }, [activePetitionId, selectedPetitionId])

  // Tempo é métrica global separada — não entra nas notas da petição.

  const timeByEvaluatorId = useMemo(() => {
    const map = new Map<string, ReadingTimeEntry>()
    for (const item of data?.items ?? []) {
      if (item.evaluator_id) map.set(item.evaluator_id, item)
    }
    return map
  }, [data])

  const timeCohortComplete = (data?.summary.count ?? 0) >= 30

  const sortedValidations = useMemo(
    () =>
      [...validations].sort((a, b) =>
        a.reviewer_name.localeCompare(b.reviewer_name, 'pt-BR', {
          sensitivity: 'base',
        }),
      ),
    [validations],
  )

  const sortedTimes = useMemo(
    () =>
      [...(data?.items ?? [])].sort((a, b) =>
        a.lawyer_name.localeCompare(b.lawyer_name, 'pt-BR', {
          sensitivity: 'base',
        }),
      ),
    [data],
  )

  const validationsPageCount = totalPages(sortedValidations.length)
  const timesPageCount = totalPages(sortedTimes.length)
  const pagedValidations = paginate(sortedValidations, validationsPage)
  const pagedTimes = paginate(sortedTimes, timesPage)

  useEffect(() => {
    if (validationsPage > validationsPageCount - 1) {
      setValidationsPage(Math.max(0, validationsPageCount - 1))
    }
  }, [validationsPage, validationsPageCount])

  useEffect(() => {
    if (timesPage > timesPageCount - 1) {
      setTimesPage(Math.max(0, timesPageCount - 1))
    }
  }, [timesPage, timesPageCount])

  const lawyerAverages = useMemo(() => {
    if (validations.length === 0) return null
    const scores = Object.fromEntries(
      SCORE_FIELDS.map(([key]) => [
        key,
        average(
          validations
            .map((validation) => Number(validation.human_scores[key]))
            .filter((value) => Number.isFinite(value)),
        ),
      ]),
    ) as Record<(typeof SCORE_FIELDS)[number][0], number | null>
    return {
      count: validations.length,
      scores,
      general: average(
        validations
          .map((validation) => Number(validation.general_score))
          .filter((value) => Number.isFinite(value)),
      ),
      applicationUseYesPercent: Math.round(
        (validations.filter((validation) => Number(validation.application_use_score) >= 50)
          .length /
          validations.length) *
        100,
      ),
      applicationUseYesCount: validations.filter(
        (validation) => Number(validation.application_use_score) >= 50,
      ).length,
    }
  }, [validations])

  const appAverages = useMemo(() => {
    if (!selectedSnapshot) return null
    const scores = selectedSnapshot.scores
    return {
      count: 1,
      scores: Object.fromEntries(
        SCORE_FIELDS.map(([key]) => [key, scores[key] ?? null]),
      ) as Record<(typeof SCORE_FIELDS)[number][0], number | null>,
      general: scores.geral ?? null,
      latest: selectedSnapshot,
    }
  }, [selectedSnapshot])

  useEffect(() => {
    load()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    if (!activePetitionId) return
    setSelectedPetitionId(activePetitionId)
    void load(activePetitionId)
    if (activePrototypeScores) {
      setProblemAssessments(
        prototypeProblems.map((problem) => ({ problem, verdict: '' })),
      )
    }
  }, [activePetitionId, activePrototypeScores, prototypeProblems])

  async function handlePetitionChange(nextId: string) {
    setSelectedPetitionId(nextId)
    setEditingValidationId(null)
    setEvaluatorId('')
    clearScoreFields()
    setTimeInput('')
    setFeedback(null)
    setValidationsPage(0)
    if (!nextId) {
      setValidations([])
      setEvaluators((await listEvaluators()).items)
      return
    }
    try {
      setValidations((await listHumanValidations(nextId)).items)
      setEvaluators((await listEvaluators(nextId)).items)
    } catch (err) {
      setFeedback(err instanceof Error ? err.message : 'Falha ao filtrar petição.')
    }
  }

  function clearScoreFields() {
    setHumanScores({})
    setGeneralScore('')
    setApplicationUseAnswer('')
    setProblemAssessments([])
    setDocumentationOk(false)
    setTextualCohesionOk(false)
    setArgumentativeConsistencyOk(false)
    setLegalBasisOk(false)
  }

  function startValidationEdit(validation: HumanValidationPayload) {
    setEditingValidationId(validation.validation_id)
    setEvaluatorId(validation.evaluator_id || '')
    setHumanScores(
      Object.fromEntries(
        SCORE_FIELDS.map(([key]) => [
          key,
          toPercentDisplay(validation.human_scores[key]),
        ]),
      ),
    )
    setGeneralScore(toPercentDisplay(validation.general_score))
    setApplicationUseAnswer(yesNoFromScore(validation.application_use_score))
    setProblemAssessments(validation.problem_assessments)
    setDocumentationOk(validation.documentation_ok)
    setTextualCohesionOk(validation.textual_cohesion_ok)
    setArgumentativeConsistencyOk(validation.argumentative_consistency_ok)
    setLegalBasisOk(validation.legal_basis_ok)
    setFeedback(null)
    requestAnimationFrame(() => {
      evaluatorSelectRef.current?.scrollIntoView({ behavior: 'smooth', block: 'center' })
      evaluatorSelectRef.current?.focus()
    })
  }

  function cancelValidationEdit() {
    setEditingValidationId(null)
    setEvaluatorId('')
    clearScoreFields()
    setFeedback(null)
  }

  function onTimeEvaluatorChange(nextId: string) {
    setTimeEvaluatorId(nextId)
    const existing = nextId ? timeByEvaluatorId.get(nextId) : undefined
    if (existing) {
      setEditingTimeEntryId(existing.entry_id)
      setTimeInput(minutesToTimeInput(existing.minutes))
    } else {
      setEditingTimeEntryId(null)
      setTimeInput('')
    }
    setTimeFeedback(null)
  }

  function cancelTimeEdit() {
    setEditingTimeEntryId(null)
    setTimeEvaluatorId('')
    setTimeInput('')
    setTimeFeedback(null)
  }

  async function handleTimeSubmit(event: React.FormEvent) {
    event.preventDefault()
    if (!timeEvaluatorId) {
      setTimeFeedback('Selecione o avaliador.')
      return
    }
    const normalizedTime = finalizeTimeInput(timeInput)
    setTimeInput(normalizedTime)
    const minutes = parseTimeToMinutes(normalizedTime)
    if (minutes == null) {
      setTimeFeedback('Informe o tempo no formato hh:mm (ex.: 08:30).')
      return
    }
    setSubmittingTime(true)
    setTimeFeedback(null)
    try {
      if (editingTimeEntryId) {
        await updateReadingTime(editingTimeEntryId, {
          evaluatorId: timeEvaluatorId,
          minutes,
        })
        setTimeFeedback('Tempo atualizado.')
      } else {
        await submitReadingTime({ evaluatorId: timeEvaluatorId, minutes })
        setTimeFeedback('Tempo registrado.')
      }
      cancelTimeEdit()
      setData(withPrototypeSummary(await listReadingTimes()))
    } catch (err) {
      setTimeFeedback(err instanceof Error ? err.message : 'Falha ao salvar tempo.')
    } finally {
      setSubmittingTime(false)
    }
  }

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault()
    if (!selectedPetitionId) {
      setFeedback('Selecione uma petição analisada pela aplicação.')
      return
    }
    if (!evaluatorId) {
      setFeedback('Selecione o avaliador.')
      return
    }
    if (!editingValidationId && campaignComplete) {
      setFeedback(`Campanha completa (${requiredEvaluations}/${requiredEvaluations}).`)
      return
    }
    const selectedEvaluator = evaluators.find((item) => item.evaluator_id === evaluatorId)
    if (
      !editingValidationId &&
      selectedEvaluator?.has_responded &&
      selectedEvaluator.validation_id
    ) {
      const existing = validations.find(
        (item) => item.validation_id === selectedEvaluator.validation_id,
      )
      if (existing) {
        startValidationEdit(existing)
        setFeedback('Este avaliador já respondeu. Edite a resposta existente.')
        return
      }
    }

    const humanValues: Record<string, number> = {}
    for (const [key] of SCORE_FIELDS) {
      const humanScore = parsePercent(humanScores[key] ?? '')
      if (humanScore == null) {
        setFeedback('Preencha a confiança (0–100%) em todas as dimensões.')
        return
      }
      humanValues[key] = humanScore
    }
    const parsedGeneralScore = parsePercent(generalScore)
    const parsedApplicationUseScore = scoreFromYesNo(applicationUseAnswer)
    if (parsedGeneralScore == null) {
      setFeedback('Preencha a confiança geral (0–100%).')
      return
    }
    if (parsedApplicationUseScore == null) {
      setFeedback('Informe se utilizaria esta aplicação (SIM ou NÃO).')
      return
    }

    setSubmitting(true)
    setFeedback(null)
    const payload = {
      petition_id: selectedPetitionId,
      evaluator_id: evaluatorId,
      human_scores: humanValues,
      problem_assessments: problemAssessments.filter(
        (item): item is ProblemAssessment => Boolean(item.verdict),
      ),
      documentation_ok: documentationOk,
      textual_cohesion_ok: textualCohesionOk,
      argumentative_consistency_ok: argumentativeConsistencyOk,
      legal_basis_ok: legalBasisOk,
      general_score: parsedGeneralScore,
      application_use_score: parsedApplicationUseScore,
      comments: '',
    }
    try {
      if (editingValidationId) {
        await updateHumanValidation(editingValidationId, payload)
        cancelValidationEdit()
        setFeedback('Avaliação humana atualizada.')
      } else {
        await submitHumanValidation(payload)
        setEvaluatorId('')
        clearScoreFields()
        setFeedback('Registro salvo.')
      }
      await load(selectedPetitionId)
    } catch (err) {
      setFeedback(err instanceof Error ? err.message : 'Falha ao salvar.')
    } finally {
      setSubmitting(false)
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

  async function handleExportChart() {
    if (!chartRef.current) {
      setFeedback('Gráfico indisponível para exportar.')
      return
    }
    try {
      await exportChartPng(chartRef.current, 'grafico_tempos_leitura.png')
      setFeedback('Gráfico de tempos exportado.')
    } catch (err) {
      setFeedback(err instanceof Error ? err.message : 'Falha ao exportar gráfico.')
    }
  }

  async function handleDeletePetition() {
    if (!selectedPetitionId || !selectedSnapshot) return
    const completed = campaign?.completed ?? validations.length
    const label = shortPetitionLabel(selectedSnapshot)
    const confirmed = window.confirm(
      `Excluir a petição analisada?\n\n${label}\n\nIsso remove o snapshot da aplicação e ${completed} avaliação(ões) humana(s) desta campanha. Tempos globais e o cadastro dos 30 avaliadores são preservados.`,
    )
    if (!confirmed) return
    try {
      const result = await deleteAnalyzedPetition(selectedPetitionId)
      cancelValidationEdit()
      setSelectedPetitionId('')
      setValidations([])
      await load('')
      setFeedback(
        `Petição excluída (${result.deleted_validations} avaliação${result.deleted_validations === 1 ? '' : 'ões'
        } humana${result.deleted_validations === 1 ? '' : 's'} removida${result.deleted_validations === 1 ? '' : 's'
        }).`,
      )
    } catch (err) {
      setFeedback(err instanceof Error ? err.message : 'Falha ao excluir petição.')
    }
  }

  async function handleDeleteValidation(validation: HumanValidationPayload) {
    if (!window.confirm(`Excluir a avaliação de ${validation.reviewer_name}?`)) return
    const keepPetition = selectedPetitionId
    try {
      await deleteHumanValidation(validation.validation_id)
      if (editingValidationId === validation.validation_id) {
        cancelValidationEdit()
      }
      await load(keepPetition)
      setFeedback('Avaliação humana excluída.')
    } catch (err) {
      setFeedback(err instanceof Error ? err.message : 'Falha ao excluir avaliação.')
    }
  }

  const globalReadingItems = data?.items ?? []
  const globalReadingMean = data?.summary.mean_minutes ?? null
  const globalAppSeconds =
    data?.summary.prototype_mean_seconds ?? PROTOTYPE_MEAN_SECONDS
  const globalAppLabel = data?.summary.prototype_mean_label ?? '1,3 s'
  const globalSpeedup =
    data?.summary.speedup_factor ??
    (globalReadingMean != null && globalAppSeconds > 0
      ? Math.round((globalReadingMean * 60) / globalAppSeconds)
      : null)

  return (
    <div className="dashboard">
      {loading && <p className="dashboard-hint">Carregando registros…</p>}
      {error && <div className="error-banner">{error}</div>}

      {data && (
        <>

          <section className="dashboard-section chart-section">
            <div className="dashboard-section-header">
              <h3 className="dashboard-section-title">Tempos de avaliação (eficiência)</h3>
              <button
                type="button"
                className="new-chat-btn export-btn"
                disabled={globalReadingItems.length === 0}
                onClick={handleExportChart}
              >
                Exportar gráfico (PNG)
              </button>
            </div>
            <p className="dashboard-hint">
              Agregado de <strong>todas</strong> as petições — só duração, sem filtro pela
              petição selecionada e sem relação com as notas.
            </p>
            <ReadingTimeChart
              ref={chartRef}
              items={globalReadingItems}
              meanMinutes={globalReadingMean}
              prototypeMeanSeconds={globalAppSeconds}
              prototypeMeanLabel={globalAppLabel}
            />
          </section>

          <section className="dashboard-section chart-section pie-chart-section">
            <div className="dashboard-section-header">
              <h3 className="dashboard-section-title">Comparação de tempo humano × aplicação</h3>
              <div className="export-actions">
                <button
                  type="button"
                  className="new-chat-btn export-btn"
                  disabled={globalReadingMean == null}
                  onClick={handleExportPie}
                >
                  Exportar pizza (PNG)
                </button>
              </div>
            </div>
            <ComparisonPieChart
              ref={pieRef}
              humanMeanMinutes={globalReadingMean}
              humanMeanLabel={data.summary.mean_label}
              prototypeMeanSeconds={globalAppSeconds}
              prototypeMeanLabel={globalAppLabel}
              speedupFactor={globalSpeedup}
            />
          </section>

          <div className="dashboard-cards">
            <div className="dashboard-card">
              <span className="dashboard-card-value">
                {data.summary.mean_label ?? '—'}
              </span>
              <span className="dashboard-card-label">Tempo médio humano</span>
              <span className="dashboard-card-meta">
                {data.summary.count}{' '}
                {data.summary.count === 1 ? 'registro' : 'registros'} · todas as petições
              </span>
            </div>
            <div className="dashboard-card">
              <span className="dashboard-card-value">{globalAppLabel}</span>
              <span className="dashboard-card-label">Tempo médio da aplicação</span>
              <span className="dashboard-card-meta">
                {data.summary.prototype_measurements ?? 0}{' '}
                {(data.summary.prototype_measurements ?? 0) === 1
                  ? 'medição'
                  : 'medições'}{' '}
                · todas as petições
              </span>
            </div>
            <div className="dashboard-card">
              <span className="dashboard-card-value">
                {globalSpeedup != null ? `${globalSpeedup}×` : '—'}
              </span>
              <span className="dashboard-card-label">Ganho de velocidade</span>
              <span className="dashboard-card-meta">humano ÷ aplicação (global)</span>
            </div>
          </div>


          <section className="dashboard-section averages-section">
            <h3 className="dashboard-section-title">
              Notas da aplicação × avaliação humana
            </h3>
            <p className="dashboard-hint">
              Qualidade (0–100%) da petição selecionada — distinta dos tempos globais acima.
            </p>

            <div className="petition-campaign-bar">
              <label className="validation-field">
                Petição analisada
                <select
                  value={selectedPetitionId}
                  onChange={(event) => void handlePetitionChange(event.target.value)}
                >
                  <option value="">Selecione…</option>
                  {(appEvaluations?.items ?? [])
                    .filter((item) => item.petition_id)
                    .map((item) => (
                      <option key={item.entry_id} value={item.petition_id || ''}>
                        {shortPetitionLabel(item)}
                      </option>
                    ))}
                </select>
              </label>
              {selectedPetitionId && (
                <div className="campaign-progress" aria-live="polite">
                  <strong>
                    {campaign?.completed ?? validations.length} de {requiredEvaluations}
                  </strong>
                  <span>
                    {(campaign?.remaining ??
                      Math.max(0, requiredEvaluations - validations.length))}{' '}
                    avaliações restantes
                    {campaignComplete ? ' · campanha completa' : ''}
                  </span>
                </div>
              )}
              {selectedPetitionId && (
                <button
                  type="button"
                  className="link-btn danger-btn"
                  onClick={() => void handleDeletePetition()}
                >
                  Excluir petição
                </button>
              )}
            </div>
            {!selectedPetitionId && (
              <p className="dashboard-hint">
                Analise uma petição no chat para iniciar uma campanha de 30 avaliadores.
              </p>
            )}

            <div className="criteria-comparison-footer">
              <span>
                Aplicação: snapshot da petição selecionada
              </span>
              <span>
                Avaliação humana:{' '}
                <strong>{lawyerAverages?.count ?? 0}</strong>{' '}
                {lawyerAverages?.count === 1 ? 'registro' : 'registros'}
              </span>
              {lawyerAverages && (
                <span>
                  Utilizaria esta aplicação:{' '}
                  <strong>{lawyerAverages.applicationUseYesPercent}% SIM</strong>
                </span>
              )}
            </div>
            {selectedPetitionId && (appAverages || lawyerAverages) ? (
              <>
                <div className="criteria-comparison-grid">
                  {[
                    ...SCORE_FIELDS.map(([key, label]) => ({
                      key,
                      label,
                      app: appAverages?.scores[key] ?? null,
                      human: lawyerAverages?.scores[key] ?? null,
                    })),
                    {
                      key: 'geral',
                      label: 'Geral',
                      app: appAverages?.general ?? null,
                      human: lawyerAverages?.general ?? null,
                    },
                  ].map((criterion) => (
                    <article className="criterion-comparison-card" key={criterion.key}>
                      <h4>{criterion.label}</h4>
                      <div className="criterion-score criterion-score--app">
                        <span>Aplicação</span>
                        <strong>
                          {criterion.app != null ? `${Math.round(criterion.app)}%` : '—'}
                        </strong>
                      </div>
                      <div className="criterion-score criterion-score--human">
                        <span>Avaliação humana</span>
                        <strong>
                          {criterion.human != null
                            ? `${Math.round(criterion.human)}%`
                            : '—'}
                        </strong>
                      </div>
                    </article>
                  ))}
                </div>

                <ScoreComparisonChart
                  criteria={[
                    ...SCORE_FIELDS.map(([key]) => ({
                      label: SCORE_CHART_LABELS[key],
                      application: appAverages?.scores[key] ?? null,
                      human: lawyerAverages?.scores[key] ?? null,
                    })),
                    {
                      label: 'Geral',
                      application: appAverages?.general ?? null,
                      human: lawyerAverages?.general ?? null,
                    },
                  ]}
                  acceptancePercent={
                    lawyerAverages?.applicationUseYesPercent ?? null
                  }
                  evaluatorCount={lawyerAverages?.count ?? 0}
                />
              </>
            ) : (
              <p className="dashboard-hint">
                Selecione uma petição analisada para comparar notas da aplicação e
                avaliações humanas.
              </p>
            )}
          </section>

          <section className="dashboard-section">
            <h3 className="dashboard-section-title">
              {editingValidationId
                ? 'Editar avaliação humana'
                : 'Registrar avaliação humana'}
            </h3>
            <form className="reading-form" onSubmit={handleSubmit}>
              <label className="validation-field">
                Avaliador *
                <select
                  ref={evaluatorSelectRef}
                  value={evaluatorId}
                  onChange={(event) => setEvaluatorId(event.target.value)}
                  required
                  disabled={!selectedPetitionId || (!editingValidationId && campaignComplete)}
                >
                  <option value="">Selecione…</option>
                  {evaluators.map((evaluator) => {
                    const blocked =
                      !editingValidationId &&
                      evaluator.has_responded &&
                      evaluator.validation_id !== editingValidationId
                    return (
                      <option
                        key={evaluator.evaluator_id}
                        value={evaluator.evaluator_id}
                        disabled={blocked && !editingValidationId}
                      >
                        {evaluator.name}
                        {evaluator.has_responded ? ' (já respondeu)' : ''}
                      </option>
                    )
                  })}
                </select>
              </label>
              <div className="validation-scores lawyer-scores-only">
                <strong>Notas do avaliador (0% a 100%)</strong>
                {SCORE_FIELDS.map(([key, label]) => (
                  <label className="validation-score-field" key={key}>
                    <span className="validation-score-label">{label}</span>
                    <input
                      type="text"
                      inputMode="numeric"
                      aria-label={`${label} - nota %`}
                      placeholder={`80%`}
                      value={percentInputValue(humanScores[key] ?? '')}
                      onChange={(event) =>
                        onPercentInputChange(event.target.value, (next) =>
                          setHumanScores({
                            ...humanScores,
                            [key]: next,
                          }),
                        )
                      }
                      required
                      disabled={!selectedPetitionId || (!editingValidationId && campaignComplete)}
                    />
                  </label>
                ))}
                <label className="validation-score-field">
                  <span className="validation-score-label">Geral</span>
                  <input
                    type="text"
                    inputMode="numeric"
                    aria-label="Geral - nota %"
                    value={percentInputValue(generalScore)}
                    placeholder={`80%`}
                    onChange={(event) =>
                      onPercentInputChange(event.target.value, setGeneralScore)
                    }
                    required
                    disabled={!selectedPetitionId || (!editingValidationId && campaignComplete)}
                  />
                </label>
                <fieldset className="validation-score-field validation-score-field--use yes-no-field">
                  <legend className="validation-score-label">Utilizaria esta aplicação</legend>
                  <div className="yes-no-options" role="radiogroup" aria-label="Utilizaria esta aplicação">
                    <label className="yes-no-option">
                      <input
                        type="radio"
                        name="application-use"
                        value="sim"
                        checked={applicationUseAnswer === 'sim'}
                        onChange={() => setApplicationUseAnswer('sim')}
                        required
                        disabled={!selectedPetitionId || (!editingValidationId && campaignComplete)}
                      />
                      SIM
                    </label>
                    <label className="yes-no-option">
                      <input
                        type="radio"
                        name="application-use"
                        value="nao"
                        checked={applicationUseAnswer === 'nao'}
                        onChange={() => setApplicationUseAnswer('nao')}
                        required
                        disabled={!selectedPetitionId || (!editingValidationId && campaignComplete)}
                      />
                      NÃO
                    </label>
                  </div>
                </fieldset>
              </div>
              <div className="validation-actions">
                <button
                  type="submit"
                  className="primary-btn"
                  disabled={
                    submitting ||
                    !selectedPetitionId ||
                    !evaluatorId ||
                    !applicationUseAnswer ||
                    (!editingValidationId && campaignComplete)
                  }
                >
                  {submitting
                    ? 'Salvando…'
                    : editingValidationId
                      ? 'Salvar edição'
                      : campaignComplete
                        ? 'Campanha completa'
                        : 'Registrar'}
                </button>
                {editingValidationId && (
                  <button
                    type="button"
                    className="link-btn"
                    onClick={cancelValidationEdit}
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

          <section className="dashboard-section">
            <h3 className="dashboard-section-title">Registros de avaliação humana</h3>
            {sortedValidations.length > 0 ? (
              <>
                <div className="validation-records-table-wrap">
                  <table className="validation-records-table">
                    <thead>
                      <tr>
                        <th scope="col" className="validation-record-index">
                          #
                        </th>
                        <th scope="col">Nome do avaliador</th>
                        {SCORE_FIELDS.map(([, label]) => (
                          <th scope="col" key={label}>
                            {label}
                          </th>
                        ))}
                        <th scope="col">Geral</th>
                        <th scope="col">Utilizaria</th>
                        <th scope="col">
                          <span className="sr-only">Ações</span>
                        </th>
                      </tr>
                    </thead>
                    <tbody>
                      {pagedValidations.map((validation, index) => {
                        const rowNumber = validationsPage * PAGE_SIZE + index + 1
                        return (
                          <tr key={validation.validation_id}>
                            <td className="validation-record-index">{rowNumber}</td>
                            <th scope="row">{validation.reviewer_name}</th>
                            {SCORE_FIELDS.map(([key, label]) => (
                              <td key={label}>
                                {toPercentDisplay(validation.human_scores[key]) || '—'}%
                              </td>
                            ))}
                            <td>{toPercentDisplay(validation.general_score) || '—'}%</td>
                            <td>{yesNoLabel(validation.application_use_score)}</td>
                            <td className="validation-record-actions-cell">
                              <button
                                type="button"
                                className="link-btn"
                                onClick={() => startValidationEdit(validation)}
                              >
                                Editar
                              </button>
                              <button
                                type="button"
                                className="link-btn danger-btn"
                                onClick={() => handleDeleteValidation(validation)}
                              >
                                Excluir
                              </button>
                            </td>
                          </tr>
                        )
                      })}
                    </tbody>
                  </table>
                </div>
                <div className="table-pagination" role="navigation" aria-label="Paginação das avaliações">
                  <button
                    type="button"
                    className="link-btn"
                    disabled={validationsPage <= 0}
                    onClick={() => setValidationsPage((page) => Math.max(0, page - 1))}
                  >
                    Anterior
                  </button>
                  <span>
                    Página {validationsPage + 1} de {validationsPageCount} ·{' '}
                    {sortedValidations.length} registro
                    {sortedValidations.length === 1 ? '' : 's'}
                  </span>
                  <button
                    type="button"
                    className="link-btn"
                    disabled={validationsPage >= validationsPageCount - 1}
                    onClick={() =>
                      setValidationsPage((page) =>
                        Math.min(validationsPageCount - 1, page + 1),
                      )
                    }
                  >
                    Próxima
                  </button>
                </div>
              </>
            ) : (
              <p className="dashboard-hint">
                {selectedPetitionId
                  ? 'Nenhuma avaliação humana registrada nesta petição.'
                  : 'Selecione uma petição para ver os registros.'}
              </p>
            )}
          </section>
        
          <section className="dashboard-section">
            <h2 className="dashboard-section-title">
              {editingTimeEntryId
                ? 'Editar tempo de avaliação'
                : 'Registrar tempo de avaliação'}
            </h2>
            <p className="dashboard-hint">
              Um tempo por avaliador (máx. 29). Serve só às métricas de eficiência — sem
              relação com as notas por petição.
            </p>
            <form className="reading-form" onSubmit={handleTimeSubmit}>
              <label className="validation-field">
                Avaliador *
                <select
                  value={timeEvaluatorId}
                  onChange={(event) => onTimeEvaluatorChange(event.target.value)}
                  required
                  disabled={!editingTimeEntryId && timeCohortComplete}
                >
                  <option value="">Selecione…</option>
                  {allEvaluators.map((evaluator) => {
                    const hasTime = timeByEvaluatorId.has(evaluator.evaluator_id)
                    const blocked = !editingTimeEntryId && hasTime
                    return (
                      <option
                        key={evaluator.evaluator_id}
                        value={evaluator.evaluator_id}
                        disabled={blocked}
                      >
                        {evaluator.name}
                        {hasTime ? ' (já registrado)' : ''}
                      </option>
                    )
                  })}
                </select>
              </label>
              <label className="validation-field reading-time-field">
                Tempo de avaliação humana (hh:mm) *
                <input
                  type="text"
                  inputMode="numeric"
                  autoComplete="off"
                  maxLength={4}
                  value={timeInput}
                  onChange={(e) => setTimeInput(formatTimeDigits(e.target.value))}
                  onBlur={() => setTimeInput((current) => finalizeTimeInput(current))}
                  placeholder="ex.: 7:30"
                  required
                  disabled={!editingTimeEntryId && timeCohortComplete}
                />
              </label>
              <div className="validation-actions">
                <button
                  type="submit"
                  className="primary-btn"
                  disabled={
                    submittingTime ||
                    !timeEvaluatorId ||
                    !timeInput.trim() ||
                    (!editingTimeEntryId && timeCohortComplete)
                  }
                >
                  {submittingTime
                    ? 'Salvando…'
                    : editingTimeEntryId
                      ? 'Salvar tempo'
                      : timeCohortComplete
                        ? '29/30 tempos'
                        : 'Registrar tempo'}
                </button>
                {editingTimeEntryId && (
                  <button type="button" className="link-btn" onClick={cancelTimeEdit}>
                    Cancelar
                  </button>
                )}
                {timeFeedback && (
                  <span className="validation-feedback">{timeFeedback}</span>
                )}
              </div>
            </form>
            {(sortedTimes.length > 0) && (
              <>
                <div className="validation-records-table-wrap" style={{ marginTop: '0rem' }}>
                  <table className="validation-records-table">
                    <thead>
                      <tr>
                        <th scope="col">#</th>
                        <th scope="col">Avaliador</th>
                        <th scope="col">Tempo</th>
                        <th scope="col">
                          <span className="sr-only">Ações</span>
                        </th>
                      </tr>
                    </thead>
                    <tbody>
                      {pagedTimes.map((item, index) => {
                        const rowNumber = timesPage * PAGE_SIZE + index + 1
                        return (
                          <tr key={item.entry_id}>
                            <td>{rowNumber}</td>
                            <th scope="row">{item.lawyer_name}</th>
                            <td>{minutesToLabel(item.minutes)}</td>
                            <td className="validation-record-actions-cell">
                              <button
                                type="button"
                                className="link-btn"
                                onClick={() =>
                                  onTimeEvaluatorChange(item.evaluator_id || '')
                                }
                              >
                                Editar
                              </button>
                            </td>
                          </tr>
                        )
                      })}
                    </tbody>
                  </table>
                </div>
                <div className="table-pagination" role="navigation" aria-label="Paginação dos tempos">
                  <button
                    type="button"
                    className="link-btn"
                    disabled={timesPage <= 0}
                    onClick={() => setTimesPage((page) => Math.max(0, page - 1))}
                  >
                    Anterior
                  </button>
                  <span>
                    Página {timesPage + 1} de {timesPageCount} · {sortedTimes.length}{' '}
                    registro{sortedTimes.length === 1 ? '' : 's'}
                  </span>
                  <button
                    type="button"
                    className="link-btn"
                    disabled={timesPage >= timesPageCount - 1}
                    onClick={() =>
                      setTimesPage((page) => Math.min(timesPageCount - 1, page + 1))
                    }
                  >
                    Próxima
                  </button>
                </div>
              </>
            )}
          </section>

 

        
        </>
      )}
    </div>
  )
}
