import { useEffect, useMemo, useRef, useState } from 'react'
import axios from 'axios'

type AutoConfigResponse = {
  brands: string[]
  markets_by_brand: Record<string, string[]>
  default_brand: string
  default_markets: string[]
}

type DebugPlanStep = {
  id: string
  step_type: 'filter' | 'comparison' | 'ranking' | 'exclude_markets' | 'exclude_filter' | 'exclude_ranking'
  enabled: boolean
  metric_key?: string
  metric_label?: string
  kind?: 'trend' | 'band' | 'threshold'
  operator?: string
  value?: string | number
  left_metric_key?: string
  left_metric_label?: string
  right_metric_key?: string
  right_metric_label?: string
  direction?: 'below' | 'above' | 'ascending' | 'descending'
  limit?: number
  market?: string
  source_text: string
  input_count?: number
  matched_markets?: string[]
}

type SegmentResult = {
  id: string
  label: string
  action_direction: string
  steps: DebugPlanStep[]
  execution_order: string[]
  matched_markets: string[]
}

type ExceptionMarket = {
  market: string
  action_direction: string
  reason: string
}

type MarketDisposition = {
  market: string
  tier: 't1' | 't2' | 't3' | 't4' | 't5' | 'excluded'
  col: number          // 0-4 for t1-t5, -1 for excluded
  action: string
  score: number
  score_pct: number
  criteria_met: number
  criteria_total: number
  segment?: string | null
  is_exception?: boolean
}

type ScoringTier = {
  col: number
  id: string
  range: string
  action: string
}

type DebugInterpretation = {
  goal: string
  task_types: string[]
  entity: string
  action_direction: string
  is_multi_segment?: boolean
  segments?: SegmentResult[]
  exceptions?: ExceptionMarket[]
  steps: DebugPlanStep[]
  execution_order: string[]
  assumptions: string[]
  reasoning: string
  matched_markets: string[]
  market_dispositions?: MarketDisposition[]
  scoring_tiers?: ScoringTier[]
  conflict_resolutions?: ConflictResolution[]
  resolved_market_actions?: ResolvedMarketAction[]
}

type DebugHitl = {
  needs_review: boolean
  confidence: number
  summary: string
  review_reason: string[]
  options: string[]
}

type DebugResponse = {
  status: string
  selection: { brand: string; markets: string[]; markets_count: number; baseline_budget?: number }
  market_intelligence_guidance: { source_file?: string | null; matched_row_count?: number; notes?: string[] }
  provider: string
  model: string
  ai_prompt: string
  raw_text: string
  parsed_json?: unknown
  normalized_interpretation?: DebugInterpretation
  hitl?: DebugHitl
  notes: string[]
}

type ApprovedPlanMarketReview = {
  market: string
  action_direction: string
  action_family: string
  source_label: string
  verdict: 'supported' | 'mixed' | 'at_risk' | 'needs_data'
  score: number
  overall_media_elasticity: number | null
  responsiveness_label: string
  avg_cpr: number | null
  avg_cpr_band: string | null
  brand_salience: number | null
  brand_salience_band: string | null
  change_in_market_share: number | null
  change_in_brand_equity: number | null
  supporting_points: string[]
  warning_points: string[]
  summary: string
}

type ApprovedPlanAiReason = {
  market: string
  reason: string
}

type ApprovedPlanAiReview = {
  provider: string
  model: string
  headline: string
  summary: string
  validations: string[]
  warnings: string[]
  market_green_lights: ApprovedPlanAiReason[]
  market_watchouts: ApprovedPlanAiReason[]
  raw_text: string
  notes: string[]
}

type ApprovedPlanEvaluationResponse = {
  status: string
  selection: { brand: string; markets: string[]; markets_count: number }
  approved_market_count: number
  deterministic_overview: {
    headline: string
    summary: string
    validations: string[]
    warnings: string[]
  }
  ai_review: ApprovedPlanAiReview
  market_reviews: ApprovedPlanMarketReview[]
  notes: string[]
}

type ScenarioHandoffBudgetContext = {
  baseline_budget: number
  target_budget: number
  scenario_range_lower_pct: number
  scenario_range_upper_pct: number
  scenario_budget_lower: number
  scenario_budget_upper: number
  budget_increase_type: 'percentage' | 'absolute'
  budget_increase_value: number
}

type ScenarioHandoffResolvedIntent = {
  target_markets: string[]
  protected_markets: string[]
  held_markets: string[]
  deprioritized_markets: string[]
  action_preferences_by_market: Record<string, string>
  market_action_explanations: Record<string, string>
  explanation_notes: string[]
}

type ScenarioHandoffStrategyPreview = {
  provider: string
  model: string
  summary: string
  notes: string[]
  family_mix_weights: { volume: number; revenue: number; balanced: number }
  pace_preference: string
  coverage_preference: string
  diversity_preference: string
  budget_zone_preference: string
}

type ScenarioHandoffResponse = {
  status: string
  selection: { brand: string; markets: string[]; markets_count: number }
  approved_market_count: number
  budget_context: ScenarioHandoffBudgetContext
  resolved_intent: ScenarioHandoffResolvedIntent
  strategy_preview: ScenarioHandoffStrategyPreview
  suggested_job_payload: Record<string, unknown>
  notes: string[]
}

type ScenarioJobCreateResponse = {
  job_id: string
  status: 'queued' | 'running' | 'completed' | 'failed' | 'expired'
  ready: boolean
  progress?: number
  message?: string
}

type ScenarioJobStatusResponse = {
  job_id: string
  ready: boolean
  status: 'queued' | 'running' | 'completed' | 'failed' | 'expired'
  progress: number
  message: string
  error_reason?: string | null
}

type ScenarioMarketRow = {
  market: string
  old_total_spend: number
  new_total_spend: number
  new_budget_share: number
  fy25_reach_share_pct?: number
  new_reach_share_pct?: number
  pct_change_total_spend?: number
  revenue_uplift_pct?: number
  uplift_pct?: number
  new_total_tv_spend?: number
  new_total_digital_spend?: number
  fy25_tv_reach?: number
  fy25_digital_reach?: number
  tv_cpr?: number
  digital_cpr?: number
  tv_split?: number
  digital_split?: number
  fy25_tv_share?: number
  fy25_digital_share?: number
}

type ScenarioItem = {
  scenario_id: string
  scenario_index: number
  family: string
  seed_source: string
  volume_uplift_pct: number
  revenue_uplift_pct: number
  balanced_score: number
  total_new_spend: number
  markets: ScenarioMarketRow[]
}

type ScenarioReachFilter = {
  markets: string[]
  direction: 'higher' | 'lower'
}

type SavedScenarioPlan = {
  saved_at: string
  brand: string
  prompt: string
  scenario_id: string
  family: string
  split_view: 'reach' | 'spend'
  metrics: {
    volume_uplift_pct: number
    revenue_uplift_pct: number
    budget_utilized_pct: number
  }
  guidance: {
    resolved_intent: ScenarioHandoffResolvedIntent | null
    strategy_preview: ScenarioHandoffStrategyPreview | null
  }
  markets: ScenarioMarketRow[]
}

type ScenarioResultsResponse = {
  ready: boolean
  job_id: string
  status: 'completed'
  summary: {
    scenario_count: number
    target_count: number
    selected_brand: string
    selected_markets: string[]
    target_budget: number
    baseline_budget: number
    strategy: {
      family_mix_weights: { volume: number; revenue: number; balanced: number }
      pace_preference: string
      coverage_preference: string
      diversity_preference: string
    }
  }
  generation_notes: string[]
  pagination: {
    total_count: number
    total_pages: number
    page: number
    page_size: number
    sort_key: string
    sort_dir: 'asc' | 'desc'
  }
  items: ScenarioItem[]
}

type ConflictResolutionCandidate = {
  action_direction: string
  source_label: string
  score: number
  verdict: 'supported' | 'mixed' | 'at_risk' | 'needs_data'
  reason: string
}

type ConflictResolution = {
  market: string
  candidate_actions: ConflictResolutionCandidate[]
  chosen_action_direction: string
  chosen_source_label: string
  reason: string
}

type ResolvedMarketAction = {
  market: string
  action_direction: string
  action_family: string
  source_label: string
  conflict_reason?: string
}

type Props = { apiBaseUrl: string; config: AutoConfigResponse | null }

type Phase = 'idle' | 'loading' | 'revealing' | 'done'
type HitlMode = 'review' | 'feedback' | 'approved'

function stepLabel(step: DebugPlanStep): string {
  switch (step.step_type) {
    case 'comparison':
      return `${step.left_metric_label} ${step.operator} ${step.right_metric_label}`
    case 'filter':
      if (step.kind === 'trend') {
        return `${step.metric_label} is ${step.operator === '<' ? 'decreasing ↓' : 'increasing ↑'}`
      }
      return `${step.metric_label} is ${step.operator === '<=' ? 'low' : 'high'}`
    case 'ranking':
      return `Top ${step.limit} by ${step.metric_label}`
    case 'exclude_markets':
      return `Exclude: ${step.market}`
    case 'exclude_ranking':
      return `Remove top ${step.limit} by ${step.metric_label}`
    case 'exclude_filter':
      return `Remove where ${step.metric_label} ${step.operator} ${step.value}${step.kind === 'threshold' ? '%' : ''}`
    default:
      return step.source_text ?? step.id
  }
}

function stepAccent(type: DebugPlanStep['step_type']): {
  dot: string; bg: string; text: string; badge: string
} {
  if (type === 'comparison') return { dot: 'bg-violet-400', bg: 'bg-violet-50', text: 'text-violet-700', badge: 'bg-violet-100 text-violet-700' }
  if (type === 'filter') return { dot: 'bg-blue-400', bg: 'bg-blue-50', text: 'text-blue-700', badge: 'bg-blue-100 text-blue-700' }
  if (type === 'ranking') return { dot: 'bg-sky-400', bg: 'bg-sky-50', text: 'text-sky-700', badge: 'bg-sky-100 text-sky-700' }
  if (type === 'exclude_ranking') return { dot: 'bg-rose-400', bg: 'bg-rose-50', text: 'text-rose-700', badge: 'bg-rose-100 text-rose-700' }
  if (type === 'exclude_filter') return { dot: 'bg-orange-400', bg: 'bg-orange-50', text: 'text-orange-700', badge: 'bg-orange-100 text-orange-700' }
  return { dot: 'bg-rose-400', bg: 'bg-rose-50', text: 'text-rose-700', badge: 'bg-rose-100 text-rose-700' }
}

function isExclusion(type: DebugPlanStep['step_type']) {
  return type === 'exclude_markets' || type === 'exclude_filter' || type === 'exclude_ranking'
}

function segmentAccent(action: string): { bg: string; text: string; badge: string; dot: string } {
  const a = action.toLowerCase()
  if (a === 'increase') return { bg: 'bg-emerald-50', text: 'text-emerald-700', badge: 'bg-emerald-100 text-emerald-700', dot: 'bg-emerald-500' }
  if (a === 'slight_increase' || a === 'slight increase') return { bg: 'bg-teal-50', text: 'text-teal-700', badge: 'bg-teal-100 text-teal-700', dot: 'bg-teal-400' }
  if (a === 'decrease' || a === 'reduce' || a === 'deprioritize') return { bg: 'bg-rose-50', text: 'text-rose-700', badge: 'bg-rose-100 text-rose-700', dot: 'bg-rose-400' }
  if (a === 'slight_decrease' || a === 'slight decrease') return { bg: 'bg-amber-50', text: 'text-amber-700', badge: 'bg-amber-100 text-amber-700', dot: 'bg-amber-400' }
  return { bg: 'bg-slate-50', text: 'text-slate-600', badge: 'bg-slate-100 text-slate-600', dot: 'bg-slate-400' }
}

function formatActionLabel(action: string) {
  return action.replace(/_/g, ' ')
}

export function BudgetAllocationDebugPage({ apiBaseUrl, config }: Props) {
  const [brand, setBrand] = useState('')
  const [markets, setMarkets] = useState<string[]>([])
  const [prompt, setPrompt] = useState('')
  const [setupCollapsed, setSetupCollapsed] = useState(false)
  const [budgetIncreasePct, setBudgetIncreasePct] = useState(5)
  const [scenarioRangeLowerPct, setScenarioRangeLowerPct] = useState(80)
  const [scenarioRangeUpperPct, setScenarioRangeUpperPct] = useState(120)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [result, setResult] = useState<DebugResponse | null>(null)
  const [phase, setPhase] = useState<Phase>('idle')
  const [visibleCount, setVisibleCount] = useState(0)
  const [hitlMode, setHitlMode] = useState<HitlMode>('review')
  const [feedbackText, setFeedbackText] = useState('')
  const [feedbackLoading, setFeedbackLoading] = useState(false)
  const [expandedSteps, setExpandedSteps] = useState<Record<string, boolean>>({})
  const [approvalEvaluation, setApprovalEvaluation] = useState<ApprovedPlanEvaluationResponse | null>(null)
  const [approvalLoading, setApprovalLoading] = useState(false)
  const [approvalError, setApprovalError] = useState('')
  const [scenarioHandoff, setScenarioHandoff] = useState<ScenarioHandoffResponse | null>(null)
  const [scenarioHandoffLoading, setScenarioHandoffLoading] = useState(false)
  const [scenarioHandoffError, setScenarioHandoffError] = useState('')
  const [scenarioJobId, setScenarioJobId] = useState('')
  const [scenarioStatus, setScenarioStatus] = useState<'idle' | 'queued' | 'running' | 'completed' | 'failed' | 'expired'>('idle')
  const [scenarioProgress, setScenarioProgress] = useState(0)
  const [scenarioMessage, setScenarioMessage] = useState('')
  const [scenarioError, setScenarioError] = useState('')
  const [scenarioResults, setScenarioResults] = useState<ScenarioResultsResponse | null>(null)
  const [scenarioPage, setScenarioPage] = useState(1)
  const [scenarioSortKey, setScenarioSortKey] = useState('revenue_uplift_pct')
  const [scenarioSortDir] = useState<'asc' | 'desc'>('desc')
  const [scenarioMinVolumePct, setScenarioMinVolumePct] = useState('')
  const [scenarioMinRevenuePct, setScenarioMinRevenuePct] = useState('')
  const [scenarioMaxBudgetUtilizedPctFilter, setScenarioMaxBudgetUtilizedPctFilter] = useState('')
  const [scenarioSectionCollapsed, setScenarioSectionCollapsed] = useState(false)
  const [scenarioReachFilters, setScenarioReachFilters] = useState<ScenarioReachFilter[]>([
    { markets: [], direction: 'higher' },
    { markets: [], direction: 'lower' },
  ])
  const [resultsCollapsed, setResultsCollapsed] = useState(false)
  const [, setQaFeedbackText] = useState('')
  const [qaSectionCollapsed, setQaSectionCollapsed] = useState(false)
  const [expandedQaCards, setExpandedQaCards] = useState<Record<string, boolean>>({})
  const [qaActionSelections, setQaActionSelections] = useState<Record<string, string>>({})
  const [qaSaveMessage, setQaSaveMessage] = useState('')
  const [scenarioModal, setScenarioModal] = useState<ScenarioItem | null>(null)
  const [scenarioModalSplitView, setScenarioModalSplitView] = useState<'reach' | 'spend'>('reach')
  const [scenarioModalSortBy, setScenarioModalSortBy] = useState<'budget_delta' | 'brand_salience' | 'market_share_change'>('budget_delta')
  const [scenarioModalChangeFilter, setScenarioModalChangeFilter] = useState<'all' | 'increase' | 'decrease'>('all')
  const [scenarioMarketDetailRow, setScenarioMarketDetailRow] = useState<(ScenarioMarketRow & { deltaBudget: number }) | null>(null)
  const [scoringGridCollapsed, setScoringGridCollapsed] = useState(true)
  const [scenarioPlanMessage, setScenarioPlanMessage] = useState('')
  const [savedScenarioPlans, setSavedScenarioPlans] = useState<SavedScenarioPlan[]>([])
  const [savedPlansOpen, setSavedPlansOpen] = useState(false)
  const [openReachFilterIndex, setOpenReachFilterIndex] = useState<number | null>(null)
  const [zoomAnchor, setZoomAnchor] = useState<ScenarioItem | null>(null)
  const [zoomBandPct, setZoomBandPct] = useState(5)
  const [zoomPrompt, setZoomPrompt] = useState('')
  const [zoomLoading, setZoomLoading] = useState(false)
  const [zoomJobId, setZoomJobId] = useState('')
  const [zoomStatus, setZoomStatus] = useState<'idle' | 'queued' | 'running' | 'completed' | 'failed' | 'expired'>('idle')
  const [zoomProgress, setZoomProgress] = useState(0)
  const [zoomMessage, setZoomMessage] = useState('')
  const [zoomResults, setZoomResults] = useState<ScenarioResultsResponse | null>(null)
  const [zoomError, setZoomError] = useState('')
  const [zoomPage, setZoomPage] = useState(1)
  const [zoomSortKey, setZoomSortKey] = useState('balanced_score')
  const [zoomSortDir] = useState<'asc' | 'desc'>('desc')
  const [zoomMinVolumePct, setZoomMinVolumePct] = useState('')
  const [zoomMinRevenuePct, setZoomMinRevenuePct] = useState('')
  const [zoomMaxBudgetUtilizedPctFilter, setZoomMaxBudgetUtilizedPctFilter] = useState('')
  const [zoomReachFilters, setZoomReachFilters] = useState<ScenarioReachFilter[]>([
    { markets: [], direction: 'higher' },
    { markets: [], direction: 'lower' },
  ])
  const [openZoomReachFilterIndex, setOpenZoomReachFilterIndex] = useState<number | null>(null)
  const revealTimer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const savedPlansRef = useRef<HTMLDivElement | null>(null)
  const reachFiltersRef = useRef<HTMLDivElement | null>(null)
  const zoomReachFiltersRef = useRef<HTMLDivElement | null>(null)
  const zoomPanelRef = useRef<HTMLDivElement | null>(null)

  useEffect(() => {
    if (!config) return
    const next = config.default_brand || config.brands[0] || ''
    setBrand(next)
    setMarkets(config.markets_by_brand[next] ?? [])
    setSetupCollapsed(false)
  }, [config])

  useEffect(() => {
    try {
      const raw = window.localStorage.getItem('mba.savedScenarioPlans')
      if (!raw) {
        setSavedScenarioPlans([])
        return
      }
      const parsed = JSON.parse(raw) as SavedScenarioPlan[]
      setSavedScenarioPlans(Array.isArray(parsed) ? parsed : [])
    } catch {
      setSavedScenarioPlans([])
    }
  }, [])

  useEffect(() => {
    function handlePointerDown(event: MouseEvent) {
      const target = event.target as Node
      if (savedPlansOpen && savedPlansRef.current && !savedPlansRef.current.contains(target)) {
        setSavedPlansOpen(false)
      }
      if (openReachFilterIndex !== null && reachFiltersRef.current && !reachFiltersRef.current.contains(target)) {
        setOpenReachFilterIndex(null)
      }
      if (openZoomReachFilterIndex !== null && zoomReachFiltersRef.current && !zoomReachFiltersRef.current.contains(target)) {
        setOpenZoomReachFilterIndex(null)
      }
    }

    document.addEventListener('mousedown', handlePointerDown)
    return () => document.removeEventListener('mousedown', handlePointerDown)
  }, [savedPlansOpen, openReachFilterIndex, openZoomReachFilterIndex])

  useEffect(() => {
    setScenarioHandoff(null)
    setScenarioHandoffError('')
  }, [budgetIncreasePct, scenarioRangeLowerPct, scenarioRangeUpperPct])

  useEffect(() => {
    setScenarioResults(null)
    setScenarioError('')
    setScenarioJobId('')
    setScenarioStatus('idle')
    setScenarioProgress(0)
    setScenarioMessage('')
    setScenarioPage(1)
  }, [brand, markets])

  useEffect(() => {
    if (!scenarioJobId) return
    if (!(scenarioStatus === 'queued' || scenarioStatus === 'running')) return
    const interval = window.setInterval(async () => {
      try {
        const response = await axios.get<ScenarioJobStatusResponse>(`${apiBaseUrl}/api/scenarios/jobs/${scenarioJobId}`)
        setScenarioStatus(response.data.status)
        setScenarioProgress(response.data.progress ?? 0)
        setScenarioMessage(response.data.message ?? '')
        if (response.data.status === 'completed') {
          window.clearInterval(interval)
          await fetchScenarioResults(scenarioJobId, 1)
        } else if (response.data.status === 'failed' || response.data.status === 'expired') {
          window.clearInterval(interval)
          setScenarioError(response.data.error_reason ?? 'Scenario generation failed.')
        }
      } catch (err) {
        window.clearInterval(interval)
        setScenarioError(axios.isAxiosError(err) ? (err.response?.data?.detail ?? 'Unable to fetch scenario job status.') : 'Unable to fetch scenario job status.')
      }
    }, 2500)
    return () => window.clearInterval(interval)
  }, [apiBaseUrl, scenarioJobId, scenarioStatus, scenarioPage, scenarioSortKey, scenarioSortDir, scenarioMinVolumePct, scenarioMinRevenuePct, scenarioMaxBudgetUtilizedPctFilter, scenarioReachFilters])

  useEffect(() => {
    if (!scenarioJobId || scenarioStatus !== 'completed') return
    void fetchScenarioResults(scenarioJobId, scenarioPage)
  }, [scenarioJobId, scenarioStatus, scenarioPage, scenarioSortKey, scenarioSortDir, scenarioMinVolumePct, scenarioMinRevenuePct, scenarioMaxBudgetUtilizedPctFilter, scenarioReachFilters])

  useEffect(() => {
    if (!zoomJobId) return
    if (!(zoomStatus === 'queued' || zoomStatus === 'running')) return
    const interval = window.setInterval(async () => {
      try {
        const response = await axios.get<ScenarioJobStatusResponse>(`${apiBaseUrl}/api/scenarios/jobs/${zoomJobId}`)
        setZoomStatus(response.data.status)
        setZoomProgress(response.data.progress ?? 0)
        setZoomMessage(response.data.message ?? '')
        if (response.data.status === 'completed') {
          window.clearInterval(interval)
          await fetchZoomResults(zoomJobId, 1)
        } else if (response.data.status === 'failed' || response.data.status === 'expired') {
          window.clearInterval(interval)
          setZoomError(response.data.error_reason ?? 'Zoom generation failed.')
          setZoomLoading(false)
        }
      } catch (err) {
        window.clearInterval(interval)
        setZoomError(axios.isAxiosError(err) ? (err.response?.data?.detail ?? 'Unable to fetch zoom job status.') : 'Unable to fetch zoom job status.')
        setZoomLoading(false)
      }
    }, 2500)
    return () => window.clearInterval(interval)
  }, [apiBaseUrl, zoomJobId, zoomStatus])

  useEffect(() => {
    if (!zoomJobId || zoomStatus !== 'completed') return
    void fetchZoomResults(zoomJobId, zoomPage)
  }, [zoomJobId, zoomStatus, zoomPage, zoomSortKey, zoomSortDir, zoomMinVolumePct, zoomMinRevenuePct, zoomMaxBudgetUtilizedPctFilter, zoomReachFilters])

  useEffect(() => {
    if (!zoomAnchor || !zoomPanelRef.current) return
    window.setTimeout(() => {
      zoomPanelRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
    }, 80)
  }, [zoomAnchor])

  const availableMarkets = useMemo(
    () => (brand && config ? config.markets_by_brand[brand] ?? [] : []),
    [config, brand],
  )

  function toggleMarket(m: string) {
    setMarkets((prev) => (prev.includes(m) ? prev.filter((x) => x !== m) : [...prev, m]))
  }

  function startReveal(steps: DebugPlanStep[]) {
    setVisibleCount(steps.length)
    setPhase('done')
  }

  function toggleStepDetails(stepKey: string) {
    setExpandedSteps((prev) => ({ ...prev, [stepKey]: !prev[stepKey] }))
  }

  async function run(mode: 'initial' | 'revise', feedback = '') {
    if (!brand) { setError('Select a brand first.'); return }
    if (revealTimer.current) clearTimeout(revealTimer.current)
    setError('')
    if (mode === 'initial') {
      setHitlMode('review')
      setResult(null)
      setPhase('loading')
      setLoading(true)
      setExpandedSteps({})
      setApprovalEvaluation(null)
      setApprovalLoading(false)
      setApprovalError('')
      setScenarioHandoff(null)
      setScenarioHandoffLoading(false)
      setScenarioHandoffError('')
      setScenarioResults(null)
      setScenarioError('')
      setScenarioJobId('')
      setScenarioStatus('idle')
      setScenarioProgress(0)
      setScenarioMessage('')
      setResultsCollapsed(false)
      setQaFeedbackText('')
    } else {
      setFeedbackLoading(true)
    }
    try {
      const res = await axios.post<DebugResponse>(`${apiBaseUrl}/api/scenarios/intent/debug`, {
        selected_brand: brand,
        selected_markets: markets,
        budget_increase_type: 'percentage',
        budget_increase_value: budgetIncreasePct,
        market_overrides: {},
        intent_prompt: prompt,
        review_mode: mode,
        user_feedback: feedback,
        current_interpretation: result?.normalized_interpretation ?? null,
      })
      setResult(res.data)
      setFeedbackText('')
      setHitlMode('review')
      const steps = res.data.normalized_interpretation?.steps ?? []
      startReveal(steps)
      setSetupCollapsed(true)
    } catch (err) {
      setPhase('idle')
      setHitlMode('review')
      setError(axios.isAxiosError(err) ? (err.response?.data?.detail ?? 'Failed.') : 'Unexpected error.')
    } finally {
      setLoading(false)
      setFeedbackLoading(false)
    }
  }

  async function prepareScenarioHandoff(approvedInterpretation: DebugInterpretation) {
    if (!brand) return
    setScenarioHandoffLoading(true)
    setScenarioHandoffError('')
    try {
      const res = await axios.post<ScenarioHandoffResponse>(`${apiBaseUrl}/api/scenarios/intent/handoff`, {
        selected_brand: brand,
        selected_markets: markets,
        budget_increase_type: 'percentage',
        budget_increase_value: budgetIncreasePct,
        market_overrides: {},
        intent_prompt: prompt,
        approved_interpretation: approvedInterpretation,
        scenario_range_lower_pct: scenarioRangeLowerPct,
        scenario_range_upper_pct: scenarioRangeUpperPct,
      })
      setScenarioHandoff(res.data)
    } catch (err) {
      setScenarioHandoff(null)
      setScenarioHandoffError(axios.isAxiosError(err) ? (err.response?.data?.detail ?? 'Failed to prepare scenario guidance.') : 'Unexpected error.')
    } finally {
      setScenarioHandoffLoading(false)
    }
  }

  async function fetchScenarioResults(jobId: string, page = scenarioPage) {
    const params: Record<string, string | number> = {
      page,
      page_size: 5,
      sort_key: scenarioSortKey,
      sort_dir: scenarioSortDir,
    }
    if (scenarioMinVolumePct.trim() !== '') params.min_volume_uplift_pct = Number(scenarioMinVolumePct)
    if (scenarioMinRevenuePct.trim() !== '') params.min_revenue_uplift_pct = Number(scenarioMinRevenuePct)
    if (scenarioMaxBudgetUtilizedPctFilter.trim() !== '') params.max_budget_utilized_pct = Number(scenarioMaxBudgetUtilizedPctFilter)
    scenarioReachFilters.slice(0, 2).forEach((filter, index) => {
      if (!filter.markets.length) return
      const suffix = index === 0 ? '' : '_2'
      params[`reach_share_market${suffix}`] = filter.markets.join(',')
      params[`reach_share_direction${suffix}`] = filter.direction
    })
    const response = await axios.get<ScenarioResultsResponse>(`${apiBaseUrl}/api/scenarios/jobs/${jobId}/results`, {
      params,
      validateStatus: (status) => [200, 202, 409, 410].includes(status),
    })
    if (response.status === 200) {
      setScenarioResults(response.data)
      setScenarioPage(response.data.pagination.page)
      setScenarioStatus('completed')
      setScenarioError('')
      return
    }
    if (response.status === 202) {
      setScenarioStatus('running')
      return
    }
    const payload = response.data as { error_reason?: string }
    setScenarioError(payload.error_reason ?? 'Failed to load scenario results.')
  }

  function setScenarioReachFilter(index: number, patch: Partial<ScenarioReachFilter>) {
    setScenarioReachFilters((prev) => prev.map((item, itemIndex) => (itemIndex === index ? { ...item, ...patch } : item)))
    setScenarioPage(1)
  }

  function setZoomReachFilter(index: number, patch: Partial<ScenarioReachFilter>) {
    setZoomReachFilters((prev) => prev.map((item, itemIndex) => (itemIndex === index ? { ...item, ...patch } : item)))
    setZoomPage(1)
  }

  async function startScenarioGeneration() {
    if (!scenarioHandoff) {
      setScenarioError('Prepare scenario guidance before generating scenarios.')
      return
    }
    setScenarioError('')
    setScenarioResults(null)
    const response = await axios.post<ScenarioJobCreateResponse>(`${apiBaseUrl}/api/scenarios/jobs`, {
      ...scenarioHandoff.suggested_job_payload,
      target_scenarios: 5000,
      max_runtime_seconds: 300,
    })
    setScenarioJobId(response.data.job_id)
    setScenarioStatus(response.data.status)
    setScenarioProgress(response.data.progress ?? 0)
    setScenarioMessage(response.data.message ?? 'Scenario generation queued.')
  }

  async function fetchZoomResults(jobId: string, page = zoomPage) {
    const params: Record<string, string | number> = {
      page,
      page_size: 5,
      sort_key: zoomSortKey,
      sort_dir: zoomSortDir,
    }
    if (zoomMinVolumePct.trim() !== '') params.min_volume_uplift_pct = Number(zoomMinVolumePct)
    if (zoomMinRevenuePct.trim() !== '') params.min_revenue_uplift_pct = Number(zoomMinRevenuePct)
    if (zoomMaxBudgetUtilizedPctFilter.trim() !== '') params.max_budget_utilized_pct = Number(zoomMaxBudgetUtilizedPctFilter)
    zoomReachFilters.slice(0, 2).forEach((filter, index) => {
      if (!filter.markets.length) return
      const suffix = index === 0 ? '' : '_2'
      params[`reach_share_market${suffix}`] = filter.markets.join(',')
      params[`reach_share_direction${suffix}`] = filter.direction
    })
    const response = await axios.get<ScenarioResultsResponse>(`${apiBaseUrl}/api/scenarios/jobs/${jobId}/results`, {
      params,
      validateStatus: (status) => [200, 202, 409, 410].includes(status),
    })
    if (response.status === 200) {
      setZoomResults(response.data)
      setZoomPage(response.data.pagination.page)
      setZoomStatus('completed')
      setZoomError('')
      setZoomLoading(false)
      return
    }
    if (response.status === 202) {
      setZoomStatus('running')
      return
    }
    const payload = response.data as { error_reason?: string }
    setZoomError(payload.error_reason ?? 'Failed to load zoom results.')
    setZoomLoading(false)
  }

  function openZoomModal(anchor: ScenarioItem) {
    setZoomAnchor(anchor)
    setZoomBandPct(5)
    setZoomPrompt('')
    setZoomLoading(false)
    setZoomJobId('')
    setZoomStatus('idle')
    setZoomProgress(0)
    setZoomMessage('')
    setZoomResults(null)
    setZoomError('')
    setZoomPage(1)
    setZoomSortKey('balanced_score')
    setZoomMinVolumePct('')
    setZoomMinRevenuePct('')
    setZoomMaxBudgetUtilizedPctFilter('')
    setZoomReachFilters([
      { markets: [], direction: 'higher' },
      { markets: [], direction: 'lower' },
    ])
    setOpenZoomReachFilterIndex(null)
  }

  function closeZoomModal() {
    setZoomAnchor(null)
    setZoomLoading(false)
    setZoomJobId('')
    setZoomStatus('idle')
    setZoomProgress(0)
    setZoomMessage('')
    setZoomResults(null)
    setZoomError('')
    setZoomPage(1)
    setOpenZoomReachFilterIndex(null)
  }

  async function startZoomGeneration(anchor: ScenarioItem) {
    if (!scenarioHandoff) return
    setZoomAnchor(anchor)
    setZoomResults(null)
    setZoomError('')
    setZoomStatus('queued')
    setZoomProgress(0)
    setZoomMessage('')
    setZoomLoading(true)
    setZoomPage(1)
    try {
      let jobPayload = { ...scenarioHandoff.suggested_job_payload }

      if (zoomPrompt.trim()) {
        const reviseRes = await axios.post<DebugResponse>(`${apiBaseUrl}/api/scenarios/intent/debug`, {
          selected_brand: brand,
          selected_markets: markets,
          budget_increase_type: 'percentage',
          budget_increase_value: budgetIncreasePct,
          market_overrides: {},
          intent_prompt: prompt,
          review_mode: 'revise',
          user_feedback: zoomPrompt.trim(),
          current_interpretation: result?.normalized_interpretation ?? null,
        })
        const handoffRes = await axios.post<ScenarioHandoffResponse>(`${apiBaseUrl}/api/scenarios/intent/handoff`, {
          selected_brand: brand,
          selected_markets: markets,
          budget_increase_type: 'percentage',
          budget_increase_value: budgetIncreasePct,
          market_overrides: {},
          intent_prompt: prompt,
          approved_interpretation: reviseRes.data.normalized_interpretation,
          scenario_range_lower_pct: scenarioRangeLowerPct,
          scenario_range_upper_pct: scenarioRangeUpperPct,
        })
        jobPayload = { ...handoffRes.data.suggested_job_payload }
      }

      const bandLower = anchor.total_new_spend * (1 - zoomBandPct / 100)
      const bandUpper = anchor.total_new_spend * (1 + zoomBandPct / 100)
      const response = await axios.post<ScenarioJobCreateResponse>(`${apiBaseUrl}/api/scenarios/jobs`, {
        ...jobPayload,
        scenario_budget_lower: bandLower,
        scenario_budget_upper: bandUpper,
        scenario_label_prefix: `Near ${scenarioDisplayName(anchor)}`,
        target_scenarios: 1000,
        max_runtime_seconds: 120,
      })
      setZoomJobId(response.data.job_id)
      setZoomStatus(response.data.status)
      setZoomProgress(response.data.progress ?? 0)
      setZoomMessage(response.data.message ?? 'Zoom generation queued.')
    } catch (err) {
      setZoomError(axios.isAxiosError(err) ? (err.response?.data?.detail ?? 'Failed to start zoom generation.') : 'Unexpected error.')
      setZoomStatus('failed')
      setZoomLoading(false)
    }
  }

  async function handleApprove() {
    if (!interp || !brand) return
    setHitlMode('approved')
    setQaFeedbackText('')
    setApprovalLoading(true)
    setApprovalEvaluation(null)
    setApprovalError('')
    setScenarioHandoff(null)
    setScenarioHandoffError('')
    try {
      const res = await axios.post<ApprovedPlanEvaluationResponse>(`${apiBaseUrl}/api/scenarios/intent/evaluate-approved`, {
        selected_brand: brand,
        selected_markets: markets,
        budget_increase_type: 'percentage',
        budget_increase_value: budgetIncreasePct,
        market_overrides: {},
        intent_prompt: prompt,
        approved_interpretation: interp,
      })
      setApprovalEvaluation(res.data)
      await prepareScenarioHandoff(interp)
    } catch (err) {
      setApprovalEvaluation(null)
      setApprovalError(axios.isAxiosError(err) ? (err.response?.data?.detail ?? 'Failed to evaluate the approved plan.') : 'Unexpected error.')
    } finally {
      setApprovalLoading(false)
    }
  }

  const interp = result?.normalized_interpretation ?? null
  const hitl = result?.hitl ?? null
  const steps = interp?.steps ?? []
  const visibleSteps = steps.slice(0, visibleCount)
  const allRevealed = phase === 'done'
  const finalMarkets = interp?.matched_markets ?? []

  // Scoring grid data — available after backend returns scoring_tiers
  const scoringTiers = interp?.scoring_tiers ?? []
  const dispositions = interp?.market_dispositions ?? []
  const activeDispositions = dispositions.filter((d) => d.col >= 0)
  const excludedDispositions = dispositions.filter((d) => d.col < 0)
  const showScoringGrid = allRevealed && scoringTiers.length > 0 && dispositions.length > 0
  const conflictResolutions = interp?.conflict_resolutions ?? []
  const handoffIncreaseMarkets = scenarioHandoff?.resolved_intent.target_markets ?? []
  const handoffDecreaseMarkets = scenarioHandoff?.resolved_intent.deprioritized_markets ?? []
  const handoffHoldMarkets = [
    ...(scenarioHandoff?.resolved_intent.protected_markets ?? []),
    ...(scenarioHandoff?.resolved_intent.held_markets ?? []),
  ]
  const scenarioGenerationActive = scenarioStatus === 'queued' || scenarioStatus === 'running'
  const zoomGenerationActive = zoomStatus === 'queued' || zoomStatus === 'running'

  const confidencePct = hitl ? Math.round(hitl.confidence * 100) : null
  const confColor = confidencePct == null ? '' : confidencePct >= 85 ? 'text-emerald-600' : confidencePct >= 65 ? 'text-amber-600' : 'text-red-500'
  const approvalHeadline = approvalEvaluation?.ai_review.headline || approvalEvaluation?.deterministic_overview.headline || ''
  const approvalSummary = approvalEvaluation?.ai_review.summary || approvalEvaluation?.deterministic_overview.summary || ''
  const supportedReviews = approvalEvaluation?.market_reviews.filter((review) => review.verdict === 'supported') ?? []
  const mixedReviews = approvalEvaluation?.market_reviews.filter((review) => review.verdict === 'mixed') ?? []
  const atRiskReviews = approvalEvaluation?.market_reviews.filter((review) => review.verdict === 'at_risk') ?? []
  const orderedMarketReviews = approvalEvaluation
    ? [...approvalEvaluation.market_reviews].sort((left, right) => {
        const order = { at_risk: 0, mixed: 1, supported: 2, needs_data: 3 } as const
        return order[left.verdict] - order[right.verdict]
      })
    : []
  const bySalienceDesc = (left: ApprovedPlanMarketReview, right: ApprovedPlanMarketReview) => {
    const leftSalience = Number(left.brand_salience ?? Number.NEGATIVE_INFINITY)
    const rightSalience = Number(right.brand_salience ?? Number.NEGATIVE_INFINITY)
    if (rightSalience !== leftSalience) return rightSalience - leftSalience
    return left.market.localeCompare(right.market)
  }
  const supportPlanReviews = orderedMarketReviews.filter(
    (review) => review.verdict === 'supported' || review.supporting_points.length > 0,
  ).sort(bySalienceDesc)
  const needsReviewPlanReviews = orderedMarketReviews.filter(
    (review) => review.verdict === 'mixed' || review.verdict === 'at_risk' || review.warning_points.length > 0,
  ).sort(bySalienceDesc)
  const modalMarketMeta = useMemo(() => {
    const reviewMap = new Map<string, { brandSalience: number | null; marketShareChange: number | null }>()
    ;(approvalEvaluation?.market_reviews ?? []).forEach((review) => {
      reviewMap.set(review.market, {
        brandSalience: review.brand_salience ?? null,
        marketShareChange: review.change_in_market_share ?? null,
      })
    })
    return reviewMap
  }, [approvalEvaluation])

  const colStyle = [
    { bar: 'bg-emerald-500', bg: 'bg-emerald-50', border: 'border-emerald-200', head: 'text-emerald-700', score: 'text-emerald-600' },
    { bar: 'bg-teal-400',    bg: 'bg-teal-50',    border: 'border-teal-200',    head: 'text-teal-700',    score: 'text-teal-600' },
    { bar: 'bg-slate-400',   bg: 'bg-slate-50',   border: 'border-slate-200',   head: 'text-slate-600',   score: 'text-slate-500' },
    { bar: 'bg-amber-400',   bg: 'bg-amber-50',   border: 'border-amber-200',   head: 'text-amber-700',   score: 'text-amber-600' },
    { bar: 'bg-rose-400',    bg: 'bg-rose-50',    border: 'border-rose-200',    head: 'text-rose-600',    score: 'text-rose-500' },
  ]

  function getStepInputMarkets(stepIndex: number, stepsList: DebugPlanStep[], initialScope: string[]) {
    if (stepIndex <= 0) return initialScope
    return stepsList[stepIndex - 1]?.matched_markets ?? initialScope
  }

  function renderStepDetails(step: DebugPlanStep, stepIndex: number, stepsList: DebugPlanStep[], stepKey: string, initialScope: string[]) {
    const isOpen = Boolean(expandedSteps[stepKey])
    const inputMarkets = getStepInputMarkets(stepIndex, stepsList, initialScope)
    const outputMarkets = step.matched_markets ?? []
    const droppedMarkets = inputMarkets.filter((market) => !outputMarkets.includes(market))
    const resultLabel = isExclusion(step.step_type) ? 'Remaining after this step' : 'Passed this step'

    if (!isOpen) return null

    return (
      <div className="mt-2 rounded-2xl border border-slate-200 bg-white px-4 py-3">
        <div className="grid gap-3 lg:grid-cols-3">
          <div>
            <p className="text-[10px] font-bold uppercase tracking-[0.1em] text-slate-400">Input Scope</p>
            <p className="mt-1 text-xs font-semibold text-slate-700">{inputMarkets.length} markets</p>
            <div className="mt-2 flex flex-wrap gap-1.5">
              {inputMarkets.map((market) => (
                <span key={`${stepKey}-input-${market}`} className="rounded-full bg-slate-100 px-2 py-0.5 text-[10px] font-medium text-slate-600">
                  {market}
                </span>
              ))}
            </div>
          </div>
          <div>
            <p className="text-[10px] font-bold uppercase tracking-[0.1em] text-slate-400">{resultLabel}</p>
            <p className="mt-1 text-xs font-semibold text-emerald-700">{outputMarkets.length} markets</p>
            <div className="mt-2 flex flex-wrap gap-1.5">
              {outputMarkets.length === 0 ? (
                <span className="text-[11px] text-slate-400">None</span>
              ) : outputMarkets.map((market) => (
                <span key={`${stepKey}-output-${market}`} className="rounded-full bg-emerald-50 px-2 py-0.5 text-[10px] font-medium text-emerald-700">
                  {market}
                </span>
              ))}
            </div>
          </div>
          <div>
            <p className="text-[10px] font-bold uppercase tracking-[0.1em] text-slate-400">Dropped At This Step</p>
            <p className="mt-1 text-xs font-semibold text-rose-600">{droppedMarkets.length} markets</p>
            <div className="mt-2 flex flex-wrap gap-1.5">
              {droppedMarkets.length === 0 ? (
                <span className="text-[11px] text-slate-400">None</span>
              ) : droppedMarkets.map((market) => (
                <span key={`${stepKey}-dropped-${market}`} className="rounded-full bg-rose-50 px-2 py-0.5 text-[10px] font-medium text-rose-600">
                  {market}
                </span>
              ))}
            </div>
          </div>
        </div>
      </div>
    )
  }

  function formatMetric(value: number | null | undefined, digits = 2) {
    if (value == null || !Number.isFinite(value)) return 'n/a'
    return Number(value.toFixed(digits)).toString()
  }

  function formatBudgetValue(value: number | null | undefined) {
    if (value == null || !Number.isFinite(value)) return 'n/a'
    return new Intl.NumberFormat('en-IN', { maximumFractionDigits: 0 }).format(value)
  }

  function formatCompactBudgetValue(value: number | null | undefined) {
    if (value == null || !Number.isFinite(value)) return 'n/a'
    return new Intl.NumberFormat('en', {
      notation: 'compact',
      compactDisplay: 'short',
      maximumFractionDigits: Math.abs(value) >= 1_000_000_000 ? 1 : 0,
    }).format(value)
  }

  function escapeCsvValue(value: string | number | null | undefined) {
    const text = value == null ? '' : String(value)
    const escaped = text.replace(/"/g, '""')
    return /[",\n]/.test(escaped) ? `"${escaped}"` : escaped
  }

  function formatSignedPct(value: number | null | undefined, digits = 1) {
    if (value == null || !Number.isFinite(value)) return 'n/a'
    const fixed = Number(value.toFixed(digits))
    return `${fixed > 0 ? '+' : ''}${fixed}%`
  }

  function formatPlainNumber(value: number | null | undefined, digits = 1) {
    if (value == null || !Number.isFinite(value)) return 'n/a'
    return Number(value.toFixed(digits)).toString()
  }

  function scenarioBudgetUtilizedPct(item: ScenarioItem) {
    const targetBudget = Number(scenarioResults?.summary.target_budget ?? scenarioHandoff?.budget_context.target_budget ?? 0)
    if (!Number.isFinite(targetBudget) || targetBudget <= 0) return 0
    return (item.total_new_spend / targetBudget) * 100
  }

  function scenarioDisplayName(item: Pick<ScenarioItem, 'scenario_id' | 'family'> | Pick<SavedScenarioPlan, 'scenario_id' | 'family'>) {
    const rawId = String(item.scenario_id || '').trim()
    const family = String(item.family || '').trim()
    if (!family) return rawId || 'Scenario'
    const familyLower = family.toLowerCase()
    const idLower = rawId.toLowerCase()
    if (!rawId) return family
    if (idLower.startsWith(familyLower) || idLower.includes(`/ ${familyLower}`) || idLower.includes(`near ${familyLower}`)) {
      return rawId
    }
    return `${family} / ${rawId}`
  }

  function buildScenarioPlanPayload(item: ScenarioItem): SavedScenarioPlan {
    return {
      saved_at: new Date().toISOString(),
      brand,
      prompt,
      scenario_id: item.scenario_id,
      family: item.family,
      split_view: scenarioModalSplitView,
      metrics: {
        volume_uplift_pct: item.volume_uplift_pct,
        revenue_uplift_pct: item.revenue_uplift_pct,
        budget_utilized_pct: scenarioBudgetUtilizedPct(item),
      },
      guidance: {
        resolved_intent: scenarioHandoff?.resolved_intent ?? null,
        strategy_preview: scenarioHandoff?.strategy_preview ?? null,
      },
      markets: item.markets ?? [],
    }
  }

  function saveScenarioPlan(item: ScenarioItem) {
    try {
      const storageKey = 'mba.savedScenarioPlans'
      const existingRaw = window.localStorage.getItem(storageKey)
      const existing = existingRaw ? JSON.parse(existingRaw) as SavedScenarioPlan[] : []
      const payload = buildScenarioPlanPayload(item)
      const next = [
        payload,
        ...existing.filter((entry) => entry?.scenario_id !== item.scenario_id),
      ].slice(0, 20)
      window.localStorage.setItem(storageKey, JSON.stringify(next))
      setSavedScenarioPlans(next)
      setScenarioPlanMessage(`Saved ${scenarioDisplayName(item)}. You can download this plan later from the same modal.`)
    } catch {
      setScenarioPlanMessage('Could not save this plan locally.')
    }
  }

  function buildScenarioPlanCsv(plan: SavedScenarioPlan) {
    const headerRows = [
      ['Scenario ID', scenarioDisplayName(plan)],
      ['Brand', plan.brand],
      ['Prompt', plan.prompt],
      ['Family', plan.family],
      ['Split View', plan.split_view],
      ['Volume Uplift %', formatMetric(plan.metrics.volume_uplift_pct, 2)],
      ['Revenue Uplift %', formatMetric(plan.metrics.revenue_uplift_pct, 2)],
      ['Budget Utilized %', formatMetric(plan.metrics.budget_utilized_pct, 2)],
      ['Saved At', plan.saved_at],
      [],
    ]
    const marketRows = [
      ['Market', 'Old Spend', 'New Spend', 'Old Reach Share %', 'New Reach Share %', 'New Budget Share %'],
      ...plan.markets.map((row) => [
        row.market,
        Number(row.old_total_spend ?? 0),
        Number(row.new_total_spend ?? 0),
        row.fy25_reach_share_pct ?? '',
        row.new_reach_share_pct ?? '',
        Number(row.new_budget_share ?? 0) * 100,
      ]),
    ]
    return [...headerRows, ...marketRows]
      .map((row) => row.map((cell) => escapeCsvValue(cell)).join(','))
      .join('\n')
  }

  function downloadScenarioPlan(item: ScenarioItem) {
    const payload = buildScenarioPlanPayload(item)
    const csvText = buildScenarioPlanCsv(payload)
    const blob = new Blob([csvText], { type: 'text/csv;charset=utf-8;' })
    const url = window.URL.createObjectURL(blob)
    const anchor = document.createElement('a')
    anchor.href = url
    anchor.download = `${scenarioDisplayName(item).toLowerCase().replace(/[^a-z0-9]+/g, '-')}-plan.csv`
    document.body.appendChild(anchor)
    anchor.click()
    anchor.remove()
    window.URL.revokeObjectURL(url)
    setScenarioPlanMessage(`Downloaded ${scenarioDisplayName(item)} plan as CSV.`)
  }

  function downloadSavedScenarioPlan(plan: SavedScenarioPlan) {
    const csvText = buildScenarioPlanCsv(plan)
    const blob = new Blob([csvText], { type: 'text/csv;charset=utf-8;' })
    const url = window.URL.createObjectURL(blob)
    const anchor = document.createElement('a')
    anchor.href = url
    anchor.download = `${scenarioDisplayName(plan).toLowerCase().replace(/[^a-z0-9]+/g, '-')}-plan.csv`
    document.body.appendChild(anchor)
    anchor.click()
    anchor.remove()
    window.URL.revokeObjectURL(url)
  }

  function openSavedScenarioPlan(plan: SavedScenarioPlan) {
    setScenarioModal({
      scenario_id: plan.scenario_id,
      scenario_index: 0,
      family: plan.family,
      seed_source: 'saved_plan',
      volume_uplift_pct: plan.metrics.volume_uplift_pct,
      revenue_uplift_pct: plan.metrics.revenue_uplift_pct,
      balanced_score: 0,
      total_new_spend: plan.markets.reduce((sum, row) => sum + Number(row.new_total_spend ?? 0), 0),
      markets: plan.markets ?? [],
    })
    setScenarioModalSplitView(plan.split_view ?? 'reach')
    setScenarioModalSortBy('budget_delta')
    setScenarioModalChangeFilter('all')
    setScenarioPlanMessage(`Opened saved plan ${scenarioDisplayName(plan)}.`)
    setSavedPlansOpen(false)
  }

  function removeSavedScenarioPlan(planId: string) {
    const next = savedScenarioPlans.filter((plan) => plan.scenario_id !== planId)
    setSavedScenarioPlans(next)
    window.localStorage.setItem('mba.savedScenarioPlans', JSON.stringify(next))
  }

  function editScenarioPlanFromModal() {
    setScenarioModal(null)
    setResultsCollapsed(false)
    setQaSectionCollapsed(false)
    setScenarioSectionCollapsed(false)
    window.setTimeout(() => {
      document.getElementById('business-qa-check')?.scrollIntoView({ behavior: 'smooth', block: 'start' })
    }, 60)
  }

  function toggleQaCard(key: string) {
    setExpandedQaCards((prev) => ({ ...prev, [key]: !prev[key] }))
  }

  function setQaActionSelection(market: string, action: string) {
    setQaSaveMessage('')
    setQaActionSelections((prev) => ({ ...prev, [market]: action }))
  }

  function saveQaActionSelections() {
    if (!scenarioHandoff || !approvalEvaluation) return

    const toIntentAction = (action: string) => {
      if (action === 'maintain') return 'hold'
      if (action === 'slight_increase') return 'increase'
      if (action === 'slight_decrease') return 'decrease'
      return action
    }

    const updatedPreferences = { ...(scenarioHandoff.resolved_intent.action_preferences_by_market ?? {}) }
    approvalEvaluation.market_reviews.forEach((review) => {
      const selected = qaActionSelections[review.market]
      if (!selected) return
      updatedPreferences[review.market] = toIntentAction(selected)
    })

    const target_markets = Object.entries(updatedPreferences)
      .filter(([, action]) => action === 'increase' || action === 'recover')
      .map(([market]) => market)
    const protected_markets = Object.entries(updatedPreferences)
      .filter(([, action]) => action === 'protect')
      .map(([market]) => market)
    const deprioritized_markets = Object.entries(updatedPreferences)
      .filter(([, action]) => action === 'decrease' || action === 'deprioritize')
      .map(([market]) => market)
    const held_markets = Object.entries(updatedPreferences)
      .filter(([, action]) => action === 'hold' || action === 'maintain')
      .map(([market]) => market)

    const nextResolvedIntent = {
      ...scenarioHandoff.resolved_intent,
      action_preferences_by_market: updatedPreferences,
      target_markets,
      protected_markets,
      deprioritized_markets,
      held_markets,
    }

    const suggestedJobPayload = { ...(scenarioHandoff.suggested_job_payload as Record<string, unknown>) }
    const currentOverride = ((suggestedJobPayload.strategy_override as Record<string, unknown> | undefined) ?? {})
    suggestedJobPayload.resolved_intent = nextResolvedIntent
    suggestedJobPayload.strategy_override = {
      ...currentOverride,
      market_action_preferences: updatedPreferences,
    }

    setScenarioHandoff({
      ...scenarioHandoff,
      resolved_intent: nextResolvedIntent,
      suggested_job_payload: suggestedJobPayload,
    })
    setExpandedQaCards({})
    setQaSectionCollapsed(true)
    setResultsCollapsed(true)
    setQaSaveMessage('Saved QA action changes for scenario generation.')
  }

  function renderApprovalReasonBlock(
    review: ApprovedPlanMarketReview,
    tone: 'support' | 'review',
  ) {
    const cardKey = `${tone}-${review.market}`
    const isExpanded = Boolean(expandedQaCards[cardKey])
    const selectedAction = qaActionSelections[review.market] ?? review.action_direction
    const actionOptions = ['increase', 'slight_increase', 'maintain', 'slight_decrease', 'decrease']
    const reasonPoints = tone === 'support'
      ? (review.supporting_points.length ? review.supporting_points : [review.summary])
      : (review.warning_points.length ? review.warning_points : [review.summary])
    const visiblePoints = reasonPoints.slice(0, 3)
    const extraPoints = reasonPoints.slice(3)
    const toneClasses = tone === 'support'
      ? {
          card: 'border-emerald-200 bg-white/80',
          text: 'text-emerald-900',
          badge: 'bg-emerald-100 text-emerald-700',
        }
      : {
          card: 'border-rose-200 bg-white/80',
          text: 'text-rose-900',
          badge: 'bg-rose-100 text-rose-700',
        }

    return (
      <div key={cardKey} className={`rounded-2xl border px-4 py-3 ${toneClasses.card}`}>
        <div className="flex items-start justify-between gap-3">
          <div>
            <p className="text-sm font-semibold text-slate-900">{review.market}</p>
            <p className="mt-0.5 text-xs text-slate-500">{formatActionLabel(selectedAction)}</p>
          </div>
          <span className={`rounded-full px-2.5 py-1 text-[11px] font-semibold ${toneClasses.badge}`}>
            {review.verdict === 'at_risk' ? 'At risk' : review.verdict === 'supported' ? 'Supported' : review.verdict === 'mixed' ? 'Mixed' : 'Needs data'}
          </span>
        </div>
        <div className="mt-2 flex flex-wrap gap-2">
          {actionOptions.map((action) => {
            const isSelected = selectedAction === action
            return (
              <button
                key={`${review.market}-${action}`}
                type="button"
                onClick={() => setQaActionSelection(review.market, action)}
                className={`rounded-full border px-2.5 py-1 text-[11px] font-semibold transition ${
                  isSelected
                    ? 'border-[#9c7a4a] bg-[#f4ece0] text-[#7b5c33]'
                    : 'border-slate-200 bg-white text-slate-600 hover:border-slate-300'
                }`}
              >
                {formatActionLabel(action)}
              </button>
            )
          })}
        </div>
        <ul className={`mt-2 list-disc space-y-1 pl-5 text-sm leading-5 ${toneClasses.text}`}>
          {visiblePoints.map((point, index) => (
            <li key={`${review.market}-${tone}-summary-${index}`}>{point}</li>
          ))}
        </ul>
        {extraPoints.length > 0 && (
        <div className="mt-2">
          <button
            type="button"
            onClick={() => toggleQaCard(cardKey)}
            className="rounded-full border border-slate-200 bg-white px-3 py-1 text-xs font-semibold text-slate-600 transition hover:border-slate-300"
          >
            {isExpanded ? 'Hide details' : 'Open details'}
          </button>
        </div>
        )}
        <div className="mt-2 flex flex-wrap gap-2 text-xs text-slate-700">
          <span className="rounded-full border border-slate-200 bg-slate-50 px-2.5 py-1">
            <strong>Elasticity:</strong> {review.responsiveness_label} ({formatMetric(review.overall_media_elasticity)})
          </span>
          <span className="rounded-full border border-slate-200 bg-slate-50 px-2.5 py-1">
            <strong>CPR:</strong> {review.avg_cpr_band ?? 'unknown'} ({formatMetric(review.avg_cpr)})
          </span>
          <span className="rounded-full border border-slate-200 bg-slate-50 px-2.5 py-1">
            <strong>Salience:</strong> {review.brand_salience_band ?? 'unknown'} ({formatMetric(review.brand_salience, 1)})
          </span>
        </div>
        {isExpanded && (
          <div className="mt-2">
            <div className={`max-h-48 overflow-y-auto px-1 py-1 text-sm leading-5 ${toneClasses.text}`}>
              <ul className="list-disc space-y-1 pl-5">
                {extraPoints.map((point, index) => (
                  <li key={`${review.market}-${tone}-${index}`}>{point}</li>
                ))}
              </ul>
            </div>
          </div>
        )}
      </div>
    )
  }

  return (
    <div className="w-full space-y-4">

      <div ref={savedPlansRef} className="fixed right-4 top-4 z-40">
        <div className="flex flex-col items-end gap-2">
          <button
            type="button"
            onClick={() => setSavedPlansOpen((prev) => !prev)}
            className="rounded-full border border-[#d7cbb7] bg-white/95 px-3 py-2 text-[11px] font-semibold uppercase tracking-[0.14em] text-[#8c7554] shadow-sm backdrop-blur transition hover:border-[#9c7a4a]"
          >
            Saved Plans {savedScenarioPlans.length ? `· ${savedScenarioPlans.length}` : ''}
          </button>
          {savedPlansOpen ? (
            <div className="w-[22rem] rounded-3xl border border-[#e4d8c6] bg-white/98 p-3 shadow-xl backdrop-blur">
              <div className="flex items-center justify-between gap-2 px-1 pb-2">
                <div>
                  <p className="text-xs font-semibold uppercase tracking-[0.16em] text-[#8c7554]">Saved Plans</p>
                  <p className="mt-1 text-xs text-slate-500">Open a saved scenario or download it again later.</p>
                </div>
                <span className="rounded-full bg-slate-100 px-2.5 py-1 text-[11px] font-semibold text-slate-600">
                  {savedScenarioPlans.length}
                </span>
              </div>
              <div className="max-h-[24rem] space-y-2 overflow-y-auto pr-1">
                {savedScenarioPlans.length > 0 ? savedScenarioPlans.map((plan) => (
                  <div key={plan.scenario_id} className="rounded-2xl border border-slate-200 bg-slate-50 px-3 py-3">
                    <div className="flex items-start justify-between gap-2">
                      <div>
                        <p className="text-sm font-semibold text-slate-900">{scenarioDisplayName(plan)}</p>
                        <p className="mt-0.5 text-[11px] text-slate-500">{plan.brand} · {plan.family}</p>
                      </div>
                      <span className="rounded-full bg-white px-2 py-0.5 text-[10px] font-semibold text-slate-500">
                        {new Date(plan.saved_at).toLocaleDateString('en-IN', { day: 'numeric', month: 'short' })}
                      </span>
                    </div>
                    <div className="mt-2 flex flex-wrap gap-2">
                      <span className="rounded-full bg-emerald-50 px-2 py-0.5 text-[10px] font-semibold text-emerald-700">
                        Vol {formatSignedPct(plan.metrics.volume_uplift_pct, 1)}
                      </span>
                      <span className="rounded-full bg-blue-50 px-2 py-0.5 text-[10px] font-semibold text-blue-700">
                        Rev {formatSignedPct(plan.metrics.revenue_uplift_pct, 1)}
                      </span>
                      <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[10px] font-semibold text-slate-600">
                        Budget {formatMetric(plan.metrics.budget_utilized_pct, 1)}%
                      </span>
                    </div>
                    <div className="mt-3 flex flex-wrap gap-2">
                      <button
                        type="button"
                        onClick={() => openSavedScenarioPlan(plan)}
                        className="rounded-full bg-[#7b5c33] px-3 py-1 text-[11px] font-semibold text-white transition hover:bg-[#6c4f2a]"
                      >
                        Open
                      </button>
                      <button
                        type="button"
                        onClick={() => downloadSavedScenarioPlan(plan)}
                        className="rounded-full border border-slate-200 bg-white px-3 py-1 text-[11px] font-semibold text-slate-700 transition hover:border-[#9c7a4a] hover:text-[#7b5c33]"
                      >
                        Download
                      </button>
                      <button
                        type="button"
                        onClick={() => removeSavedScenarioPlan(plan.scenario_id)}
                        className="rounded-full border border-slate-200 bg-white px-3 py-1 text-[11px] font-semibold text-slate-500 transition hover:border-rose-300 hover:text-rose-600"
                      >
                        Remove
                      </button>
                    </div>
                  </div>
                )) : (
                  <div className="rounded-2xl border border-dashed border-slate-200 px-3 py-5 text-center text-sm text-slate-500">
                    No saved plans yet.
                  </div>
                )}
              </div>
            </div>
          ) : null}
        </div>
      </div>

      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-3 px-1">
        <div>
          <p className="budget-kicker">Budget Allocation 2.0</p>
          <h2 className="mt-1 text-xl font-semibold tracking-tight text-slate-950">Intent Interpreter</h2>
        </div>
        <span className="rounded-full border border-[#d7cbb7] bg-[#fbf8f1] px-3 py-1.5 text-[11px] font-semibold uppercase tracking-[0.16em] text-[#8c7554]">
          Trinity · HITL · Loop
        </span>
      </div>

      {/* Main layout */}
      <div className="space-y-4">

        <div className="budget-panel">
          {/* Header */}
          <div className="flex items-center justify-between gap-3 px-5 py-4 border-b border-[#ede4d6]">
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-[#9c8060]">Setup</p>
            {phase !== 'idle' ? (
              <button
                type="button"
                onClick={() => setSetupCollapsed((prev) => !prev)}
                className="rounded-full border border-[#d7cbb7] bg-white px-2.5 py-1 text-[11px] font-semibold text-slate-500 transition hover:border-[#9c7a4a] hover:text-[#7b5c33]"
              >
                {setupCollapsed ? 'Expand ▼' : 'Collapse ▲'}
              </button>
            ) : null}
          </div>

          {setupCollapsed && phase !== 'idle' ? (
            <div className="flex flex-wrap items-center gap-2 px-5 py-3">
              <span className="rounded-full bg-[#f4ece0] px-3 py-1 text-[11px] font-semibold text-[#7a5b31]">{brand || 'No brand'}</span>
              <span className="rounded-full bg-slate-100 px-3 py-1 text-[11px] font-semibold text-slate-600">{markets.length} markets</span>
              <span className="rounded-full bg-slate-100 px-3 py-1 text-[11px] font-semibold text-slate-600">Budget {formatSignedPct(budgetIncreasePct, 1)}</span>
              <span className="rounded-full bg-slate-100 px-3 py-1 text-[11px] font-semibold text-slate-600">Band {formatPlainNumber(scenarioRangeLowerPct, 1)}% to {formatPlainNumber(scenarioRangeUpperPct, 1)}%</span>
              {result?.selection?.baseline_budget ? (
                <span className="rounded-full bg-slate-100 px-3 py-1 text-[11px] font-semibold text-slate-600">
                  {formatCompactBudgetValue(result.selection.baseline_budget)} → <span className={budgetIncreasePct >= 0 ? 'text-emerald-600' : 'text-rose-500'}>{formatCompactBudgetValue(result.selection.baseline_budget * (1 + budgetIncreasePct / 100))}</span>
                </span>
              ) : null}
              <p className="min-w-full truncate text-xs text-slate-500">{prompt}</p>
            </div>
          ) : (
            <div className="divide-y divide-[#ede4d6]">
              {/* Top strip — Brand · Budget · Run */}
              <div className="flex min-h-[72px] divide-x divide-[#ede4d6]">
                {/* Brand */}
                <div className="flex min-w-[200px] flex-1 flex-col justify-center px-5 py-4">
                  <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-[#9c8060]">Brand</p>
                  <select
                    value={brand}
                    onChange={(e) => { setBrand(e.target.value); setMarkets(config?.markets_by_brand[e.target.value] ?? []); setSetupCollapsed(false) }}
                    className="mt-2 w-full rounded-xl border border-[#d7cbb7] bg-white px-3 py-2 text-sm font-medium text-slate-800 outline-none focus:border-[#8b6a3f] focus:ring-4 focus:ring-[#c9b79b]/30"
                  >
                    {(config?.brands ?? []).map((b) => <option key={b} value={b}>{b}</option>)}
                  </select>
                </div>

                {/* Scenario Band */}
                <div className="flex min-w-[240px] flex-1 flex-col justify-center px-5 py-4">
                  <div className="flex items-center justify-between gap-2">
                    <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-[#9c8060]">Scenario Band</p>
                    <span className="text-[10px] text-slate-400">Post approval</span>
                  </div>
                  <div className="mt-2 flex items-center gap-2">
                    <div className="relative w-full">
                      <input
                        type="number"
                        step="0.1"
                        value={scenarioRangeLowerPct}
                        onChange={(e) => setScenarioRangeLowerPct(Number(e.target.value))}
                        className="w-full rounded-xl border border-[#d7cbb7] bg-white px-3 py-2 pr-10 text-sm font-semibold text-slate-800 outline-none transition focus:border-[#8b6a3f] focus:ring-4 focus:ring-[#c9b79b]/30"
                      />
                      <span className="pointer-events-none absolute inset-y-0 right-3 flex items-center text-sm font-semibold text-[#8c7554]">%</span>
                    </div>
                    <span className="shrink-0 text-xs text-slate-300">to</span>
                    <div className="relative w-full">
                      <input
                        type="number"
                        step="0.1"
                        value={scenarioRangeUpperPct}
                        onChange={(e) => setScenarioRangeUpperPct(Number(e.target.value))}
                        className="w-full rounded-xl border border-[#d7cbb7] bg-white px-3 py-2 pr-10 text-sm font-semibold text-slate-800 outline-none transition focus:border-[#8b6a3f] focus:ring-4 focus:ring-[#c9b79b]/30"
                      />
                      <span className="pointer-events-none absolute inset-y-0 right-3 flex items-center text-sm font-semibold text-[#8c7554]">%</span>
                    </div>
                  </div>
                </div>

                {/* Run button */}
                <button
                  type="button"
                  onClick={() => run('initial')}
                  disabled={loading || !prompt.trim() || markets.length === 0}
                  className="flex w-[200px] shrink-0 flex-col items-start justify-center bg-gradient-to-br from-[#8b6a3f] to-[#6f522d] px-5 py-4 text-left text-white transition hover:from-[#7d5f38] hover:to-[#624826] disabled:cursor-not-allowed disabled:from-slate-300 disabled:to-slate-300"
                >
                  {loading ? (
                    <span className="flex items-center gap-2 text-sm font-semibold">
                      <span className="inline-block h-3.5 w-3.5 animate-spin rounded-full border-2 border-white/30 border-t-white" />
                      Interpreting…
                    </span>
                  ) : (
                    <>
                      <span className="text-[10px] font-semibold uppercase tracking-[0.16em] text-white/60">Run Trinity</span>
                      <span className="mt-1 text-sm font-bold">Interpret Prompt →</span>
                      <span className="mt-1 text-[11px] leading-4 text-white/60">Build the plan before QA and scenario generation.</span>
                    </>
                  )}
                </button>
              </div>

              {/* Bottom row — Markets + Prompt */}
              <div className="grid gap-0 xl:grid-cols-[minmax(280px,380px)_minmax(0,1fr)] divide-x divide-[#ede4d6]">
                <div className="px-5 py-4">
                  <div className="flex items-center justify-between gap-2">
                    <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-[#9c8060]">Markets <span className="font-normal normal-case tracking-normal text-slate-400">({markets.length} selected)</span></p>
                    <div className="flex gap-1.5">
                      <button type="button" onClick={() => setMarkets(availableMarkets)}
                        className="rounded-full border border-[#d7cbb7] bg-white px-2.5 py-0.5 text-[11px] font-semibold text-slate-500 hover:border-[#9c7a4a]">All</button>
                      <button type="button" onClick={() => setMarkets([])}
                        className="rounded-full border border-[#d7cbb7] bg-white px-2.5 py-0.5 text-[11px] font-semibold text-slate-500 hover:border-[#9c7a4a]">None</button>
                    </div>
                  </div>
                  <div className="mt-3 max-h-52 space-y-1 overflow-y-auto">
                    {availableMarkets.map((m) => (
                      <label key={`setup-${m}`} className={`flex cursor-pointer items-center justify-between rounded-xl border px-3 py-2 text-sm transition ${markets.includes(m) ? 'border-[#c9a87a] bg-[#f9f2e8] text-[#7a5b31]' : 'border-transparent text-slate-600 hover:bg-slate-50'}`}>
                        <span>{m}</span>
                        <input type="checkbox" checked={markets.includes(m)} onChange={() => toggleMarket(m)} className="h-3.5 w-3.5 rounded border-slate-300 text-[#7b5c33]" />
                      </label>
                    ))}
                  </div>
                </div>
                <div className="flex flex-col px-5 py-4">
                  <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-[#9c8060]">Prompt</p>
                  <textarea
                    rows={6}
                    value={prompt}
                    onChange={(e) => setPrompt(e.target.value)}
                    placeholder="e.g. Increase media where I am losing market share and brand salience is below category salience…"
                    className="mt-2 flex-1 min-h-[160px] w-full resize-none rounded-xl border border-[#d7cbb7] bg-white px-4 py-3 text-sm leading-6 text-slate-700 outline-none transition focus:border-[#8b6a3f] focus:ring-4 focus:ring-[#c9b79b]/30"
                  />
                  <div className="mt-2.5 flex flex-wrap gap-1.5">
                    {['Loss recovery', 'Salience based', 'Multi-condition'].map((tag) => (
                      <span key={tag} className="rounded-full border border-[#d7cbb7] px-2.5 py-0.5 text-[11px] text-slate-500">{tag}</span>
                    ))}
                  </div>
                </div>
              </div>

              {error ? <p className="mx-5 mb-4 rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-600">{error}</p> : null}
            </div>
          )}
        </div>

        {/* ── Left: input panel ── */}
        <div className="hidden budget-panel space-y-4 p-5">

          {/* Brand */}
          <div>
            <label className="budget-label">Brand</label>
            <select
              value={brand}
              onChange={(e) => { setBrand(e.target.value); setMarkets(config?.markets_by_brand[e.target.value] ?? []) }}
              className="mt-1.5 w-full rounded-xl border border-[#d7cbb7] bg-white px-3 py-2 text-sm text-slate-700 outline-none focus:border-[#8b6a3f] focus:ring-4 focus:ring-[#c9b79b]/30"
            >
              {(config?.brands ?? []).map((b) => <option key={b} value={b}>{b}</option>)}
            </select>
          </div>

          {/* Markets */}
          <div>
            <div className="flex items-center justify-between gap-2">
              <label className="budget-label">Markets <span className="font-normal text-slate-400">({markets.length} selected)</span></label>
              <div className="flex gap-1.5">
                <button type="button" onClick={() => setMarkets(availableMarkets)}
                  className="rounded-full border border-[#d7cbb7] bg-white px-2.5 py-0.5 text-[11px] font-semibold text-slate-500 hover:border-[#9c7a4a]">All</button>
                <button type="button" onClick={() => setMarkets([])}
                  className="rounded-full border border-[#d7cbb7] bg-white px-2.5 py-0.5 text-[11px] font-semibold text-slate-500 hover:border-[#9c7a4a]">None</button>
              </div>
            </div>
            <div className="mt-2 max-h-48 space-y-1 overflow-y-auto rounded-2xl border border-[#ece4d6] bg-[#fbf8f1] p-2">
              {availableMarkets.map((m) => (
                <label key={m} className={`flex cursor-pointer items-center justify-between rounded-xl border px-3 py-1.5 text-sm transition ${markets.includes(m) ? 'border-[#9c7a4a] bg-[#f4ece0] text-[#7a5b31]' : 'border-transparent bg-white text-slate-600 hover:border-[#d7cbb7]'}`}>
                  <span>{m}</span>
                  <input type="checkbox" checked={markets.includes(m)} onChange={() => toggleMarket(m)} className="h-3.5 w-3.5 rounded border-slate-300 text-primary" />
                </label>
              ))}
            </div>
          </div>

          <div className="space-y-3 rounded-2xl border border-[#ece4d6] bg-[#fbf8f1] p-3">
            <div>
              <label className="budget-label">Target Budget Change (%)</label>
              <input
                type="number"
                step="0.1"
                value={budgetIncreasePct}
                onChange={(e) => setBudgetIncreasePct(Number(e.target.value))}
                className="mt-1.5 w-full rounded-xl border border-[#d7cbb7] bg-white px-3 py-2 text-sm text-slate-700 outline-none transition focus:border-[#8b6a3f] focus:ring-4 focus:ring-[#c9b79b]/30"
              />
            </div>
            <div>
              <div className="flex items-center justify-between gap-2">
                <label className="budget-label">Scenario Budget Band (%)</label>
                <span className="text-[10px] font-semibold uppercase tracking-[0.12em] text-slate-400">Used after approval</span>
              </div>
              <div className="mt-1.5 grid grid-cols-2 gap-2">
                <input
                  type="number"
                  step="0.1"
                  value={scenarioRangeLowerPct}
                  onChange={(e) => setScenarioRangeLowerPct(Number(e.target.value))}
                  className="rounded-xl border border-[#d7cbb7] bg-white px-3 py-2 text-sm text-slate-700 outline-none transition focus:border-[#8b6a3f] focus:ring-4 focus:ring-[#c9b79b]/30"
                />
                <input
                  type="number"
                  step="0.1"
                  value={scenarioRangeUpperPct}
                  onChange={(e) => setScenarioRangeUpperPct(Number(e.target.value))}
                  className="rounded-xl border border-[#d7cbb7] bg-white px-3 py-2 text-sm text-slate-700 outline-none transition focus:border-[#8b6a3f] focus:ring-4 focus:ring-[#c9b79b]/30"
                />
              </div>
            </div>
          </div>

          {/* Prompt */}
          <div>
            <label className="budget-label">Prompt</label>
            <textarea
              rows={7}
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              placeholder="e.g. Increase media where I am losing market share and brand salience is below category salience…"
              className="mt-1.5 min-h-[180px] w-full resize-none rounded-2xl border border-[#d7cbb7] bg-white px-3 py-3 text-sm leading-6 text-slate-700 outline-none transition focus:border-[#8b6a3f] focus:ring-4 focus:ring-[#c9b79b]/30"
            />
          </div>

          <button
            type="button" onClick={() => run('initial')}
            disabled={loading || !prompt.trim() || markets.length === 0}
            className="w-full rounded-full bg-[#7b5c33] px-5 py-2.5 text-sm font-semibold text-white shadow-md shadow-[#7b5c33]/20 transition hover:bg-[#6c4f2a] disabled:cursor-not-allowed disabled:bg-slate-300 disabled:shadow-none"
          >
            {loading ? (
              <span className="flex items-center justify-center gap-2">
                <span className="inline-block h-3.5 w-3.5 animate-spin rounded-full border-2 border-white/30 border-t-white" />
                Interpreting…
              </span>
            ) : 'Interpret Prompt →'}
          </button>

          {error ? <p className="rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-600">{error}</p> : null}
        </div>

        {/* ── Right: live flow ── */}
        <div className="space-y-3">

          {/* Idle state */}
          {phase === 'idle' && (
            <div className="budget-panel flex min-h-[200px] items-center justify-center p-8 text-center">
              <div>
                <p className="text-3xl">🧠</p>
                <p className="mt-3 text-sm font-medium text-slate-500">Enter a prompt and hit Interpret</p>
                <p className="mt-1 text-xs text-slate-400">Trinity will break it into numbered steps — you review and refine</p>
              </div>
            </div>
          )}

          {/* Loading state */}
          {phase === 'loading' && (
            <div className="budget-panel flex min-h-[200px] items-center justify-center p-8">
              <div className="flex flex-col items-center gap-3">
                <span className="h-5 w-5 animate-spin rounded-full border-2 border-[#c9b79b] border-t-[#7b5c33]" />
                <span className="text-sm font-medium text-slate-700">Trinity is thinking…</span>
                <span className="text-xs text-slate-400">Breaking your prompt into steps</span>
              </div>
            </div>
          )}

          {/* ONE results panel — all stages inside */}
          {(phase === 'revealing' || phase === 'done') && interp && (
            <div className="budget-panel overflow-hidden">

              {/* Clickable header — always visible */}
              <button
                type="button"
                onClick={() => setResultsCollapsed(prev => !prev)}
                className="flex w-full items-start justify-between px-5 py-4 text-left"
              >
                <div>
                  <p className="text-xs font-semibold uppercase tracking-[0.16em] text-[#8c7554]">Trinity Analysis</p>
                  <p className="mt-1 text-sm font-medium text-slate-800 leading-5">{interp.goal || prompt}</p>
                  <div className="mt-1.5 flex flex-wrap items-center gap-2">
                    {hitlMode === 'approved'
                      ? <span className="rounded-full bg-emerald-100 px-2.5 py-0.5 text-[11px] font-semibold text-emerald-700">✓ Approved · {finalMarkets.length} markets</span>
                      : confidencePct != null && <span className={`rounded-full bg-slate-100 px-2.5 py-0.5 text-[11px] font-semibold ${confColor}`}>{confidencePct}% confidence</span>
                    }
                    {scenarioResults && <span className="text-xs text-slate-400">{scenarioResults.summary.scenario_count.toLocaleString()} scenarios ready</span>}
                  </div>
                </div>
                <span className="shrink-0 ml-3 rounded-full border border-[#d7cbb7] bg-white px-2.5 py-1 text-[11px] font-semibold text-slate-600">
                  {resultsCollapsed ? 'Expand ▼' : 'Collapse ▲'}
                </span>
              </button>

              {!resultsCollapsed && (
              <div className="divide-y divide-slate-100 border-t border-slate-100">

              {/* Section: Interpretation Steps + Scoring Grid */}
              <div className="px-5 py-5">
              {/* Goal */}
              <p className="text-xs font-semibold uppercase tracking-[0.16em] text-[#8c7554]">Interpreted Goal</p>
              <p className="mt-1.5 text-sm font-medium text-slate-800 leading-5">{interp.goal || prompt}</p>

              {/* Step pipeline */}
              <div className="mt-4 space-y-1.5">
                <p className="text-[11px] font-medium text-slate-400">Click any step to inspect how the filter worked.</p>
                {interp.is_multi_segment ? (
                  <>
                    {(interp.segments ?? []).map((seg) => {
                      const sa = segmentAccent(seg.action_direction)
                      return (
                        <div key={seg.id} className="space-y-1">
                          {/* Segment header */}
                          <div className={`flex items-center gap-2 rounded-lg px-3 py-1.5 ${sa.bg}`}>
                            <span className={`h-2 w-2 shrink-0 rounded-full ${sa.dot}`} />
                            <span className={`text-xs font-bold uppercase tracking-wider ${sa.text}`}>{seg.label}</span>
                            <span className={`ml-auto rounded-full px-2 py-0.5 text-[10px] font-bold ${sa.badge}`}>
                              {seg.matched_markets.length} markets → {seg.action_direction}
                            </span>
                          </div>
                          {/* Segment steps */}
                          {seg.steps.map((step, i) => {
                            const acc = stepAccent(step.step_type)
                            const outCount = step.matched_markets?.length ?? 0
                            const inCount = step.input_count ?? outCount
                            const excl = isExclusion(step.step_type)
                            const badgeText = excl ? `${outCount} remain` : inCount > 0 && outCount < inCount ? `${outCount} / ${inCount}` : `${outCount} match`
                            const stepKey = `${seg.id}:${step.id}`
                            return (
                              <div key={step.id} className="ml-4">
                                <button
                                  type="button"
                                  onClick={() => toggleStepDetails(stepKey)}
                                  className={`flex w-full items-center gap-3 rounded-xl px-3 py-2 text-left transition hover:brightness-[0.98] ${acc.bg}`}
                                >
                                  <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-white/70 text-[10px] font-bold text-slate-500">{i + 1}</span>
                                  <span className={`h-2 w-2 shrink-0 rounded-full ${acc.dot}`} />
                                  <span className={`flex-1 text-sm font-medium ${acc.text}`}>{stepLabel(step)}</span>
                                  <span className={`shrink-0 rounded-full px-2.5 py-0.5 text-xs font-semibold ${acc.badge}`}>{badgeText}</span>
                                  <span className="text-xs font-semibold text-slate-400">{expandedSteps[stepKey] ? '−' : '+'}</span>
                                  <span className="text-xs text-slate-400">✓</span>
                                </button>
                                {renderStepDetails(step, i, seg.steps, stepKey, result?.selection.markets ?? markets)}
                              </div>
                            )
                          })}
                        </div>
                      )
                    })}
                    {/* Exceptions strip */}
                    {(interp.exceptions ?? []).length > 0 && (
                      <div className="space-y-1">
                        <div className="flex items-center gap-2 rounded-lg bg-violet-50 px-3 py-1.5">
                          <span className="h-2 w-2 shrink-0 rounded-full bg-violet-400" />
                          <span className="text-xs font-bold uppercase tracking-wider text-violet-700">Exceptions</span>
                        </div>
                        {(interp.exceptions ?? []).map((exc) => (
                          <div key={exc.market} className="ml-4 flex items-center gap-3 rounded-xl bg-violet-50 px-3 py-2">
                            <span className="flex-1 text-sm font-medium text-violet-700">{exc.market}</span>
                            <span className="shrink-0 rounded-full bg-violet-100 px-2.5 py-0.5 text-xs font-semibold text-violet-700">
                              → {exc.action_direction}
                            </span>
                          </div>
                        ))}
                      </div>
                    )}
                    {conflictResolutions.length > 0 && (
                      <div className="space-y-2 pt-1">
                        <div className="rounded-2xl border border-amber-200 bg-amber-50/70 px-4 py-3">
                          <div className="flex items-start justify-between gap-3">
                            <div>
                              <p className="text-xs font-bold uppercase tracking-[0.14em] text-amber-800">Resolved Overlaps</p>
                              <p className="mt-1 text-sm text-amber-900">
                                These markets matched conflicting paths. Trinity picked the stronger action using elasticity, CPR, and brand salience.
                              </p>
                            </div>
                            <span className="rounded-full bg-amber-100 px-2.5 py-1 text-[11px] font-semibold text-amber-800">
                              {conflictResolutions.length} market{conflictResolutions.length !== 1 ? 's' : ''}
                            </span>
                          </div>
                          <div className="mt-3 space-y-2.5">
                            {conflictResolutions.map((resolution) => {
                              const chosenAccent = segmentAccent(resolution.chosen_action_direction)
                              return (
                                <div key={resolution.market} className="rounded-2xl border border-white/80 bg-white/80 px-4 py-3 shadow-sm">
                                  <div className="flex flex-wrap items-center gap-2">
                                    <p className="text-sm font-semibold text-slate-900">{resolution.market}</p>
                                    <span className={`rounded-full px-2.5 py-1 text-[11px] font-semibold ${chosenAccent.badge}`}>
                                      Final action: {formatActionLabel(resolution.chosen_action_direction)}
                                    </span>
                                  </div>
                                  <p className="mt-2 text-xs font-semibold uppercase tracking-[0.12em] text-slate-400">Matched paths</p>
                                  <div className="mt-2 flex flex-wrap gap-2">
                                    {resolution.candidate_actions.map((candidate, index) => {
                                      const candidateAccent = segmentAccent(candidate.action_direction)
                                      const isChosen =
                                        candidate.action_direction === resolution.chosen_action_direction
                                        && candidate.source_label === resolution.chosen_source_label
                                      return (
                                        <span
                                          key={`${resolution.market}-${candidate.source_label}-${candidate.action_direction}-${index}`}
                                          className={`rounded-full border px-2.5 py-1 text-[11px] font-medium ${isChosen ? 'border-slate-300 bg-slate-50 text-slate-700' : 'border-slate-200 bg-white text-slate-600'}`}
                                        >
                                          <span className={`mr-1 inline-flex rounded-full px-2 py-0.5 ${candidateAccent.badge}`}>
                                            {formatActionLabel(candidate.action_direction)}
                                          </span>
                                          {candidate.source_label}
                                        </span>
                                      )
                                    })}
                                  </div>
                                  <p className="mt-3 text-sm leading-5 text-slate-700">{resolution.reason}</p>
                                </div>
                              )
                            })}
                          </div>
                        </div>
                      </div>
                    )}
                  </>
                ) : (
                  <>
                    <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-400">Trinity's Plan — {steps.length} step{steps.length !== 1 ? 's' : ''}</p>
                    {visibleSteps.map((step, i) => {
                      const acc = stepAccent(step.step_type)
                      const outCount = step.matched_markets?.length ?? 0
                      const inCount = step.input_count ?? outCount
                      const excl = isExclusion(step.step_type)
                      const badgeText = excl
                        ? `${outCount} remain`
                        : inCount > 0 && outCount < inCount
                          ? `${outCount} / ${inCount}`
                          : `${outCount} match`
                      const stepKey = step.id
                      return (
                        <div key={step.id}>
                          <button
                            type="button"
                            onClick={() => toggleStepDetails(stepKey)}
                            className={`flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-left transition hover:brightness-[0.98] ${acc.bg}`}
                          >
                            <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-white/70 text-[10px] font-bold text-slate-500">{i + 1}</span>
                            <span className={`h-2 w-2 shrink-0 rounded-full ${acc.dot}`} />
                            <span className={`flex-1 text-sm font-medium ${acc.text}`}>{stepLabel(step)}</span>
                            <span className={`shrink-0 rounded-full px-2.5 py-0.5 text-xs font-semibold ${acc.badge}`}>{badgeText}</span>
                            <span className="text-xs font-semibold text-slate-400">{expandedSteps[stepKey] ? '−' : '+'}</span>
                            <span className="text-xs text-slate-400">✓</span>
                          </button>
                          {renderStepDetails(step, i, visibleSteps, stepKey, result?.selection.markets ?? markets)}
                        </div>
                      )
                    })}
                  </>
                )}
              </div>

              {/* 5-Column Market Scoring Grid — collapsible */}
              {showScoringGrid && (
                <div className="mt-4">
                  <button
                    type="button"
                    onClick={() => setScoringGridCollapsed(prev => !prev)}
                    className="flex w-full items-center justify-between rounded-xl border border-[#e8ddd0] bg-[#faf6f0] px-3 py-2 text-left transition hover:bg-[#f5ede0]"
                  >
                    <span className="text-xs font-semibold uppercase tracking-[0.14em] text-[#8c7554]">Market Scoring — {dispositions.length} markets</span>
                    <span className="text-xs font-semibold text-[#8c7554]">{scoringGridCollapsed ? 'Show ▼' : 'Hide ▲'}</span>
                  </button>
                </div>
              )}
              {showScoringGrid && !scoringGridCollapsed && (
                <div className="mt-2 space-y-2">
                  <div className="flex items-baseline justify-between">
                    <p className="text-xs font-semibold uppercase tracking-[0.16em] text-[#8c7554]">
                      Market Scoring — {dispositions.length} markets
                    </p>
                    <p className="text-[10px] text-slate-400">{interp?.is_multi_segment ? 'Assigned by segment · exceptions override' : 'Each column = 20% of criteria score'}</p>
                  </div>

                  {/* 5 equal columns */}
                  <div className="grid grid-cols-5 gap-1.5">
                    {scoringTiers.map((tier) => {
                      const s = colStyle[tier.col] ?? colStyle[2]
                      const group = activeDispositions.filter((d) => d.col === tier.col)
                      return (
                        <div key={tier.id} className={`rounded-xl border p-2.5 ${s.bg} ${s.border}`}>
                          <div className="space-y-0.5">
                            <p className={`text-[10px] font-bold uppercase tracking-[0.1em] ${s.head}`}>{tier.action}</p>
                          </div>
                          <div className="mt-2 h-1 w-full rounded-full bg-white/60">
                            {/* Bar shows intensity: full for Increase (col 0), half for Maintain (col 2), full for Decrease (col 4) */}
                            <div className={`h-1 rounded-full ${s.bar}`} style={{ width: `${tier.col <= 2 ? (100 - tier.col * 40) : ((tier.col - 2) * 40 + 20)}%` }} />
                          </div>
                          <div className="mt-2 space-y-1.5">
                            {group.length === 0 ? (
                              <p className="text-[10px] italic text-slate-300">—</p>
                            ) : group.map((d) => (
                              <div key={d.market}>
                                <div className="flex items-center justify-between gap-0.5">
                                  <span className="truncate text-[11px] font-medium text-slate-700 leading-tight">{d.market}</span>
                                  <span className={`shrink-0 text-[10px] font-semibold tabular-nums ${s.score}`}>
                                    {d.criteria_total > 0 ? `${d.criteria_met}/${d.criteria_total}` : '—'}
                                  </span>
                                </div>
                                <div className="mt-0.5 h-0.5 w-full rounded-full bg-white/50">
                                  <div className={`h-0.5 rounded-full ${s.bar} opacity-70`} style={{ width: `${d.score_pct}%` }} />
                                </div>
                              </div>
                            ))}
                          </div>
                          <p className={`mt-2 text-right text-[10px] font-bold ${s.head}`}>{group.length}</p>
                        </div>
                      )
                    })}
                  </div>

                  {/* Excluded strip */}
                  {excludedDispositions.length > 0 && (
                    <div className="flex flex-wrap items-center gap-2 rounded-xl border border-dashed border-rose-200 bg-rose-50/60 px-3 py-2">
                      <span className="text-[10px] font-bold uppercase tracking-[0.1em] text-rose-500">Excluded</span>
                      <span className="text-[10px] text-rose-400">·</span>
                      {excludedDispositions.map((d) => (
                        <span key={d.market} className="rounded-full bg-rose-100 px-2 py-0.5 text-[10px] font-semibold text-rose-600">
                          {d.market}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              )}
              </div>

              {/* Section: HITL */}
              {allRevealed && hitl && hitlMode !== 'approved' && (
                <div className="px-5 py-5">
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex-1">
                      <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-400">Does this look right?</p>
                      <p className="mt-1.5 text-sm text-slate-700 leading-5">{hitl.summary}</p>
                      {hitl.review_reason.length > 0 && (
                        <div className="mt-2 space-y-1">
                          {hitl.review_reason.map((r, i) => (
                            <p key={i} className="text-xs text-amber-700 leading-4">⚠ {r}</p>
                          ))}
                        </div>
                      )}
                    </div>
                    <span className={`shrink-0 text-lg font-bold tabular-nums ${confColor}`}>
                      {confidencePct}%
                    </span>
                  </div>

                  {hitlMode === 'review' && (
                    <div className="mt-4 flex gap-2.5">
                      <button
                        type="button" onClick={() => { void handleApprove() }}
                        className="flex-1 rounded-full bg-emerald-600 py-2.5 text-sm font-semibold text-white transition hover:bg-emerald-700"
                      >
                        ✓ Looks good, continue
                      </button>
                      <button
                        type="button" onClick={() => setHitlMode('feedback')}
                        className="flex-1 rounded-full border border-[#d7cbb7] bg-white py-2.5 text-sm font-semibold text-slate-700 transition hover:border-[#9c7a4a] hover:text-[#7b5c33]"
                      >
                        ✏ Refine this
                      </button>
                    </div>
                  )}

                  {hitlMode === 'feedback' && (
                    <div className="mt-4 space-y-2.5">
                      {feedbackLoading ? (
                        <div className="rounded-2xl border border-[#d7cbb7] bg-[#faf6f0] px-4 py-4">
                          <div className="flex items-center gap-3">
                            <span className="inline-block h-4 w-4 shrink-0 animate-spin rounded-full border-2 border-[#c9b79b] border-t-[#7b5c33]" />
                            <p className="text-sm font-semibold text-[#7b5c33]">Revising interpretation…</p>
                          </div>
                          <p className="mt-2 text-xs text-slate-500 leading-4 pl-7">
                            Applying your correction and freezing all other markets.
                          </p>
                          {feedbackText.trim() && (
                            <p className="mt-2 rounded-xl border border-[#e8ddd0] bg-white px-3 py-2 text-xs italic text-slate-600 leading-4 ml-7">
                              "{feedbackText.trim()}"
                            </p>
                          )}
                        </div>
                      ) : (
                        <>
                          <textarea
                            rows={3}
                            value={feedbackText}
                            onChange={(e) => setFeedbackText(e.target.value)}
                            placeholder="e.g. I meant top 5 markets by category salience, not low category salience…"
                            className="w-full resize-none rounded-2xl border border-[#d7cbb7] bg-white px-3 py-2.5 text-sm leading-6 text-slate-700 outline-none transition focus:border-[#8b6a3f] focus:ring-4 focus:ring-[#c9b79b]/30"
                            autoFocus
                          />
                          <div className="flex gap-2">
                            <button
                              type="button" onClick={() => run('revise', feedbackText)}
                              disabled={!feedbackText.trim()}
                              className="flex-1 rounded-full bg-[#7b5c33] py-2 text-sm font-semibold text-white transition hover:bg-[#6c4f2a] disabled:bg-slate-300"
                            >
                              Send to Trinity →
                            </button>
                            <button
                              type="button" onClick={() => setHitlMode('review')}
                              className="rounded-full border border-[#d7cbb7] bg-white px-4 py-2 text-sm text-slate-500 hover:text-slate-700"
                            >
                              Cancel
                            </button>
                          </div>
                        </>
                      )}
                    </div>
                  )}
                </div>
              )}

              {/* Sections: Approved banner + QA + Monte Carlo */}
              {allRevealed && hitlMode === 'approved' && (
                <>
                  {/* Approved banner */}
                  <div className="flex items-center gap-3 bg-emerald-50/50 px-5 py-4">
                    <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-emerald-100 text-emerald-700">✓</span>
                    <div>
                      <p className="text-sm font-semibold text-emerald-700">Interpretation approved</p>
                      <p className="text-xs text-slate-500 mt-0.5">{finalMarkets.length} market{finalMarkets.length !== 1 ? 's' : ''} · {interp?.is_multi_segment ? 'multi-segment plan' : `${interp?.action_direction} spend`}</p>
                    </div>
                    <button
                      type="button"
                      onClick={() => {
                        setHitlMode('review')
                        setApprovalEvaluation(null)
                        setApprovalError('')
                        setScenarioHandoff(null)
                        setScenarioHandoffError('')
                      }}
                      className="ml-auto rounded-full border border-[#d7cbb7] px-3 py-1 text-xs text-slate-500 hover:text-slate-700"
                    >
                      Revise
                    </button>
                  </div>

                  <div className="flex flex-col">
                  {/* QA section */}
                  <div id="business-qa-check" className="order-2 px-5 py-5">
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-400">Business QA Check</p>
                        <p className="mt-1 text-sm text-slate-600">This section stays separate from generated scenarios and consolidates all market reasoning into the two review buckets below.</p>
                      </div>
                      <div className="flex items-center gap-2">
                        {approvalEvaluation ? (
                          <span className="rounded-full bg-slate-100 px-3 py-1 text-[11px] font-semibold text-slate-600">
                            {approvalEvaluation.approved_market_count} markets
                          </span>
                        ) : null}
                        <button
                          type="button"
                          onClick={() => setQaSectionCollapsed((prev) => !prev)}
                          className="rounded-full border border-[#d7cbb7] bg-white px-2.5 py-1 text-[11px] font-semibold text-slate-600 transition hover:border-[#9c7a4a] hover:text-[#7b5c33]"
                        >
                          {qaSectionCollapsed ? 'Expand ▼' : 'Collapse ▲'}
                        </button>
                      </div>
                    </div>

                    {!qaSectionCollapsed && approvalLoading && (
                      <div className="mt-4 flex items-center gap-3 rounded-2xl border border-slate-200 bg-slate-50 px-4 py-4">
                        <span className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-slate-300 border-t-[#7b5c33]" />
                        <div>
                          <p className="text-sm font-semibold text-slate-700">Checking approved actions</p>
                          <p className="mt-0.5 text-xs text-slate-500">Looking for cases where high-elasticity markets are being cut or low-efficiency markets are being pushed.</p>
                        </div>
                      </div>
                    )}

                    {!qaSectionCollapsed && approvalError ? <p className="mt-4 rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-600">{approvalError}</p> : null}

                    {!qaSectionCollapsed && approvalEvaluation && (
                      <div className="mt-4 space-y-4">

                        {/* Reasoning — what Trinity understood from the prompt */}
                        <div className="rounded-2xl border border-[#e8ddd0] bg-[#faf6f0] px-4 py-4">
                          <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-[#8c7554]">What Trinity Understood</p>
                          <p className="mt-2 text-sm font-semibold text-slate-800 leading-5">{interp?.goal || prompt}</p>
                          {interp?.reasoning && (
                            <p className="mt-2 text-sm leading-6 text-slate-600">{interp.reasoning}</p>
                          )}
                          {(interp?.assumptions ?? []).length > 0 && (
                            <div className="mt-3 space-y-1">
                              {(interp?.assumptions ?? []).map((a, i) => (
                                <p key={i} className="text-xs text-slate-500 leading-4">· {a}</p>
                              ))}
                            </div>
                          )}
                          {approvalHeadline && (
                            <p className="mt-3 text-xs font-semibold text-[#7b5c33] leading-5">{approvalHeadline}</p>
                          )}
                        </div>

                        <div className="grid gap-3 lg:grid-cols-3">
                          <div className="rounded-2xl border border-emerald-200 bg-emerald-50 px-4 py-4">
                            <p className="text-xs font-bold uppercase tracking-[0.12em] text-emerald-700">Supported</p>
                            <p className="mt-2 text-3xl font-semibold text-emerald-800">{supportedReviews.length}</p>
                            <p className="mt-1 text-xs text-emerald-700">Actions where the economics line up with the recommendation.</p>
                          </div>
                          <div className="rounded-2xl border border-amber-200 bg-amber-50 px-4 py-4">
                            <p className="text-xs font-bold uppercase tracking-[0.12em] text-amber-700">Mixed</p>
                            <p className="mt-2 text-3xl font-semibold text-amber-800">{mixedReviews.length}</p>
                            <p className="mt-1 text-xs text-amber-700">Actions with both support and caution signals.</p>
                          </div>
                          <div className="rounded-2xl border border-rose-200 bg-rose-50 px-4 py-4">
                            <p className="text-xs font-bold uppercase tracking-[0.12em] text-rose-700">At Risk</p>
                            <p className="mt-2 text-3xl font-semibold text-rose-800">{atRiskReviews.length}</p>
                            <p className="mt-1 text-xs text-rose-700">Actions where responsiveness or salience conflicts with the recommendation.</p>
                          </div>
                        </div>

                        <div className="grid gap-3 lg:grid-cols-2">
                          <div className="rounded-2xl border border-emerald-200 bg-emerald-50 px-4 py-4">
                            <p className="text-xs font-bold uppercase tracking-[0.12em] text-emerald-700">What Supports The Plan</p>
                            <div className="mt-3 grid max-h-[34rem] gap-3 overflow-y-auto pr-1 sm:grid-cols-2">
                              {supportPlanReviews.length > 0
                                ? supportPlanReviews.map((review) => renderApprovalReasonBlock(review, 'support'))
                                : <p className="text-sm text-emerald-800">No support signals available.</p>}
                            </div>
                          </div>
                          <div className="rounded-2xl border border-rose-200 bg-rose-50 px-4 py-4">
                            <p className="text-xs font-bold uppercase tracking-[0.12em] text-rose-700">What Needs Review</p>
                            <div className="mt-3 grid max-h-[34rem] gap-3 overflow-y-auto pr-1 sm:grid-cols-2">
                              {needsReviewPlanReviews.length > 0
                                ? needsReviewPlanReviews.map((review) => renderApprovalReasonBlock(review, 'review'))
                                : <p className="text-sm text-rose-800">No review flags available.</p>}
                            </div>
                          </div>
                        </div>

                        <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-slate-200 bg-white px-4 py-4">
                          <div>
                            <p className="text-sm font-semibold text-slate-900">Save QA action changes</p>
                            <p className="mt-1 text-xs text-slate-500">Use this after changing increase, decrease, or maintain selections so scenario generation reflects them.</p>
                          </div>
                          <button
                            type="button"
                            onClick={saveQaActionSelections}
                            className="rounded-full bg-[#7b5c33] px-4 py-2 text-sm font-semibold text-white transition hover:bg-[#6c4f2a]"
                          >
                            Save QA Changes
                          </button>
                        </div>
                        {qaSaveMessage ? (
                          <p className="text-sm font-semibold text-emerald-700">{qaSaveMessage}</p>
                        ) : null}

                        {false && (
                        <div>
                          <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-400">Hidden Legacy QA</p>
                          <div className="mt-3 grid gap-3 lg:grid-cols-2">
                            {orderedMarketReviews.map((review) => (
                              <div key={review.market} className="rounded-2xl border border-slate-200 bg-white px-4 py-4">
                                <div className="flex items-start justify-between gap-3">
                                  <div>
                                    <p className="text-sm font-semibold text-slate-900">{review.market}</p>
                                    <p className="mt-0.5 text-xs text-slate-500">{review.action_direction} · {review.source_label}</p>
                                  </div>
                                  <span className="rounded-full border border-slate-200 bg-slate-50 px-2.5 py-1 text-[11px] font-semibold text-slate-600">
                                    {review.verdict === 'at_risk' ? 'At risk' : review.verdict === 'supported' ? 'Supported' : review.verdict === 'mixed' ? 'Mixed' : 'Needs data'}
                                  </span>
                                </div>
                                <p className="mt-3 text-sm leading-5 text-slate-700">
                                  {review.verdict === 'supported'
                                    ? (review.supporting_points[0] ?? review.summary)
                                    : review.verdict === 'mixed'
                                      ? review.summary
                                      : (review.warning_points[0] ?? review.summary)}
                                </p>
                                <div className="mt-3 flex flex-wrap gap-2">
                                  <span className="rounded-full bg-slate-100 px-2.5 py-1 text-[11px] font-medium text-slate-600">
                                    Elasticity {review.responsiveness_label} ({formatMetric(review.overall_media_elasticity)})
                                  </span>
                                  <span className="rounded-full bg-slate-100 px-2.5 py-1 text-[11px] font-medium text-slate-600">
                                    CPR {review.avg_cpr_band ?? 'unknown'} ({formatMetric(review.avg_cpr)})
                                  </span>
                                  <span className="rounded-full bg-slate-100 px-2.5 py-1 text-[11px] font-medium text-slate-600">
                                    Salience {review.brand_salience_band ?? 'unknown'} ({formatMetric(review.brand_salience, 1)})
                                  </span>
                                </div>
                              </div>
                            ))}
                          </div>
                        </div>
                        )}
                      </div>
                    )}
                  </div>

                  {false && (
                  <div className="order-1 px-5 py-5">
                    <div className="flex items-center justify-between gap-3">
                      <div>
                        <p className="text-xs font-semibold uppercase tracking-[0.16em] text-[#8c7554]">Generated Scenarios</p>
                        <p className="mt-1 text-sm text-slate-600">5,000 scenarios generated from the approved market plan.</p>
                      </div>
                      {scenarioHandoff && !scenarioResults && (
                        <button
                          type="button"
                          onClick={() => { void startScenarioGeneration() }}
                          disabled={scenarioGenerationActive}
                          className="rounded-full bg-[#7b5c33] px-4 py-2 text-sm font-semibold text-white transition hover:bg-[#6c4f2a] disabled:cursor-not-allowed disabled:bg-slate-300"
                        >
                          {scenarioGenerationActive ? 'Generating…' : 'Generate 5,000 Scenarios →'}
                        </button>
                      )}
                    </div>

                    {scenarioHandoffLoading && (
                      <div className="mt-4 flex items-center gap-3 rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3">
                        <span className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-slate-300 border-t-[#7b5c33]" />
                        <p className="text-sm font-semibold text-slate-700">Preparing generation plan…</p>
                      </div>
                    )}

                    {scenarioHandoffError ? <p className="mt-4 rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-600">{scenarioHandoffError}</p> : null}

                    {scenarioHandoff && !scenarioResults && !scenarioGenerationActive && (
                      <div className="mt-4 grid gap-3 lg:grid-cols-3">
                        <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-4">
                          <p className="text-xs font-bold uppercase tracking-[0.12em] text-slate-500">Target Budget</p>
                          <p className="mt-2 text-xl font-semibold text-slate-900">{formatBudgetValue(scenarioHandoff!.budget_context.target_budget)}</p>
                        </div>
                        <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-4">
                          <p className="text-xs font-bold uppercase tracking-[0.12em] text-slate-500">Scenario Envelope</p>
                          <p className="mt-1 text-sm font-semibold text-slate-900">{formatBudgetValue(scenarioHandoff!.budget_context.scenario_budget_lower)} – {formatBudgetValue(scenarioHandoff!.budget_context.scenario_budget_upper)}</p>
                          <p className="mt-1 text-xs text-slate-500">{formatMetric(scenarioHandoff!.budget_context.scenario_range_lower_pct, 0)}% – {formatMetric(scenarioHandoff!.budget_context.scenario_range_upper_pct, 0)}%</p>
                        </div>
                        <div className="rounded-2xl border border-emerald-200 bg-emerald-50 px-4 py-4">
                          <p className="text-xs font-bold uppercase tracking-[0.12em] text-emerald-700">Market Actions</p>
                          <p className="mt-2 text-sm font-semibold text-emerald-800">{handoffIncreaseMarkets.length} increase · {handoffDecreaseMarkets.length} decrease · {handoffHoldMarkets.length} hold</p>
                        </div>
                      </div>
                    )}

                    {scenarioGenerationActive && (
                      <div className="mt-4 rounded-2xl border border-slate-200 bg-white px-4 py-4">
                        <div className="flex items-center justify-between gap-3">
                          <p className="text-sm font-semibold text-slate-800">{scenarioMessage || 'Running scenario generation...'}</p>
                          <span className="text-sm font-semibold text-slate-500">{Math.round(scenarioProgress)}%</span>
                        </div>
                        <div className="mt-3 h-2 w-full rounded-full bg-slate-100">
                          <div className="h-2 rounded-full bg-[#7b5c33] transition-all" style={{ width: `${Math.max(4, scenarioProgress)}%` }} />
                        </div>
                      </div>
                    )}

                    {scenarioError ? <p className="mt-4 rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-600">{scenarioError}</p> : null}

                    {scenarioResults && (
                      <div className="mt-4 space-y-4">
                        {/* Summary */}
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="rounded-full bg-emerald-50 px-3 py-1.5 text-[11px] font-semibold text-emerald-700">{scenarioResults!.summary.scenario_count.toLocaleString()} scenarios</span>
                          <span className="rounded-full bg-slate-100 px-3 py-1 text-[11px] font-semibold text-slate-600">Budget {formatBudgetValue(scenarioResults!.summary.target_budget)}</span>
                          <span className="rounded-full bg-slate-100 px-3 py-1 text-[11px] font-semibold text-slate-600">{scenarioResults!.summary.selected_markets.length} markets</span>
                          <button
                            type="button"
                            onClick={() => { void startScenarioGeneration() }}
                            className="ml-auto rounded-full border border-[#d7cbb7] bg-white px-3 py-1 text-xs font-semibold text-slate-600 transition hover:border-[#9c7a4a] hover:text-[#7b5c33]"
                          >
                            Regenerate
                          </button>
                        </div>

                        {/* Filters + Sort */}
                        <div ref={reachFiltersRef} className="grid gap-3 rounded-2xl border border-slate-200 bg-white px-4 py-4 lg:grid-cols-12">
                          <div className="lg:col-span-3">
                            <label className="text-xs font-semibold uppercase tracking-[0.12em] text-slate-500">Sort by</label>
                            <select value={scenarioSortKey} onChange={(e) => { setScenarioSortKey(e.target.value); setScenarioPage(1) }}
                              className="mt-1.5 w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm text-slate-700">
                              <option value="revenue_uplift_pct">Revenue uplift</option>
                              <option value="volume_uplift_pct">Volume uplift</option>
                              <option value="balanced_score">Balanced score</option>
                            </select>
                          </div>
                          <div className="lg:col-span-3">
                            <label className="text-xs font-semibold uppercase tracking-[0.12em] text-slate-500">Min Volume Uplift %</label>
                            <input type="number" step="0.01" value={scenarioMinVolumePct}
                              onChange={(e) => { setScenarioMinVolumePct(e.target.value); setScenarioPage(1) }}
                              className="mt-1.5 w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm text-slate-700"
                              placeholder="e.g. 2.0" />
                          </div>
                          <div className="lg:col-span-3">
                            <label className="text-xs font-semibold uppercase tracking-[0.12em] text-slate-500">Min Revenue Uplift %</label>
                            <input type="number" step="0.01" value={scenarioMinRevenuePct}
                              onChange={(e) => { setScenarioMinRevenuePct(e.target.value); setScenarioPage(1) }}
                              className="mt-1.5 w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm text-slate-700"
                              placeholder="e.g. 2.5" />
                          </div>
                          <div className="lg:col-span-3">
                            <label className="text-xs font-semibold uppercase tracking-[0.12em] text-slate-500">Max Budget Utilized %</label>
                            <input type="number" step="0.01" value={scenarioMaxBudgetUtilizedPctFilter}
                              onChange={(e) => { setScenarioMaxBudgetUtilizedPctFilter(e.target.value); setScenarioPage(1) }}
                              className="mt-1.5 w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm text-slate-700"
                              placeholder="e.g. 100" />
                          </div>
                          {scenarioReachFilters.map((filter, index) => (
                            <div key={`reach-filter-${index}`} className="relative rounded-2xl border border-slate-200 bg-slate-50 px-3 py-3 lg:col-span-6">
                              <div className="flex items-center justify-between gap-2">
                                <label className="text-xs font-semibold uppercase tracking-[0.12em] text-slate-500">
                                  Reach Share Filter {index + 1}
                                </label>
                                {filter.markets.length ? (
                                  <span className="rounded-full bg-white px-2.5 py-1 text-[10px] font-semibold text-slate-600">
                                    {filter.markets.length} selected
                                  </span>
                                ) : null}
                              </div>
                              <button
                                type="button"
                                onClick={() => setOpenReachFilterIndex((prev) => (prev === index ? null : index))}
                                className="mt-3 flex w-full items-center justify-between rounded-2xl border border-slate-300 bg-white px-3 py-2.5 text-left text-sm text-slate-700 shadow-sm transition hover:border-[#9c7a4a]"
                              >
                                <span className="truncate pr-3">
                                  {filter.markets.length > 0 ? `${filter.markets.length} market${filter.markets.length !== 1 ? 's' : ''} selected` : 'Select markets'}
                                </span>
                                <span className="text-xs text-slate-400">{openReachFilterIndex === index ? '▲' : '▼'}</span>
                              </button>
                              {openReachFilterIndex === index ? (
                                <div className="absolute left-3 right-3 top-[5.5rem] z-20 rounded-2xl border border-slate-200 bg-white p-2 shadow-xl">
                                  <div className="max-h-56 space-y-1 overflow-y-auto pr-1">
                                    {(scenarioResults?.summary.selected_markets ?? markets).map((market) => {
                                      const selected = filter.markets.includes(market)
                                      return (
                                        <label
                                          key={`reach-filter-${index}-${market}`}
                                          className={`flex cursor-pointer items-center gap-3 rounded-xl px-3 py-2 text-sm transition ${selected ? 'bg-[#f4ece0] text-[#7b5c33]' : 'hover:bg-slate-50 text-slate-700'}`}
                                        >
                                          <input
                                            type="checkbox"
                                            checked={selected}
                                            onChange={(e) => {
                                              const nextMarkets = e.target.checked
                                                ? [...filter.markets, market]
                                                : filter.markets.filter((item) => item !== market)
                                              setScenarioReachFilter(index, { markets: nextMarkets })
                                            }}
                                            className="h-4 w-4 rounded border-slate-300 text-[#7b5c33] focus:ring-[#c9b79b]"
                                          />
                                          <span className="flex-1">{market}</span>
                                        </label>
                                      )
                                    })}
                                  </div>
                                  <div className="mt-2 flex items-center justify-between gap-2 border-t border-slate-100 px-2 pt-2">
                                    <button
                                      type="button"
                                      onClick={() => setScenarioReachFilter(index, { markets: [] })}
                                      className="text-xs font-semibold text-slate-500 transition hover:text-rose-600"
                                    >
                                      Clear
                                    </button>
                                    <button
                                      type="button"
                                      onClick={() => setOpenReachFilterIndex(null)}
                                      className="rounded-full bg-[#7b5c33] px-3 py-1 text-xs font-semibold text-white transition hover:bg-[#6c4f2a]"
                                    >
                                      Done
                                    </button>
                                  </div>
                                </div>
                              ) : null}
                              <select
                                value={filter.direction}
                                onChange={(e) => setScenarioReachFilter(index, { direction: e.target.value as 'higher' | 'lower' })}
                                disabled={!filter.markets.length}
                                className="mt-3 w-full rounded-2xl border border-slate-300 bg-white px-3 py-2 text-sm font-medium text-slate-700 shadow-sm disabled:bg-slate-100 disabled:text-slate-400"
                              >
                                <option value="higher">Higher than last year</option>
                                <option value="lower">Lower than last year</option>
                              </select>
                            </div>
                          ))}
                        </div>

                        {/* Scenario cards — horizontal scroll, vertical bars, click to inspect */}
                        <div className="px-1 py-2">
                          <div className="flex flex-wrap items-center justify-between gap-3">
                            <div>
                              <p className="text-sm font-semibold text-slate-900">Scenario Comparison</p>
                              <p className="mt-1 text-xs text-slate-500">Showing 5 scenarios at a time with grouped bars for volume, revenue, and budget utilised.</p>
                            </div>
                            <p className="text-[10px] text-slate-400">Click any scenario to see per-market budget breakdown.</p>
                          </div>
                          <div className="mt-5 grid gap-4 lg:grid-cols-5">
                          {scenarioResults!.items.map((item) => {
                            const budgetPct = scenarioBudgetUtilizedPct(item)
                            const volBarH = Math.max(0, Math.min(100, Math.abs(item.volume_uplift_pct) * 6.5))
                            const revBarH = Math.max(0, Math.min(100, Math.abs(item.revenue_uplift_pct) * 6.5))
                            const budBarH = Math.max(0, Math.min(100, ((budgetPct - 80) / 40) * 100))
                            const volColor = item.volume_uplift_pct >= 0 ? 'bg-emerald-500' : 'bg-rose-400'
                            const revColor = item.revenue_uplift_pct >= 0 ? 'bg-blue-500' : 'bg-rose-400'
                            const budColor = budgetPct > 100 ? 'bg-rose-400' : budgetPct > 90 ? 'bg-amber-400' : 'bg-slate-400'
                            return (
                              <button
                                key={item.scenario_id}
                                type="button"
                                onClick={() => {
                                  setScenarioModal(item)
                                  setScenarioModalSplitView('reach')
                                  setScenarioModalSortBy('budget_delta')
                                  setScenarioModalChangeFilter('all')
                                  setScenarioPlanMessage('')
                                }}
                                className="rounded-2xl border border-slate-200 bg-white px-4 py-4 text-left transition hover:border-[#9c7a4a] hover:shadow-md"
                              >
                                <div className="mb-4">
                                  <div className="flex items-center justify-between gap-2">
                                    <p className="text-sm font-semibold text-slate-900">{scenarioDisplayName(item)}</p>
                                    <span className="rounded-full bg-slate-200 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-[0.08em] text-slate-600">{item.family}</span>
                                  </div>
                                </div>
                                <div className="relative grid h-44 grid-cols-3 gap-4">
                                  <div className="pointer-events-none absolute inset-x-0 bottom-9 border-t border-slate-200" />
                                  <div className="flex flex-col items-center">
                                    <div className="relative h-32 w-full">
                                      <div className={`absolute bottom-0 left-[12%] w-[76%] rounded-t-md ${volColor}`} style={{ height: `${volBarH <= 0 ? 0 : Math.max(8, volBarH)}%` }} />
                                    </div>
                                    <span className="mt-3 text-[10px] font-bold uppercase tracking-wider text-slate-400">Volume</span>
                                    <span className="text-[11px] font-semibold tabular-nums text-slate-700">{formatSignedPct(item.volume_uplift_pct, 1)}</span>
                                  </div>
                                  <div className="flex flex-col items-center">
                                    <div className="relative h-32 w-full">
                                      <div className={`absolute bottom-0 left-[12%] w-[76%] rounded-t-md ${revColor}`} style={{ height: `${revBarH <= 0 ? 0 : Math.max(8, revBarH)}%` }} />
                                    </div>
                                    <span className="mt-3 text-[10px] font-bold uppercase tracking-wider text-slate-400">Revenue</span>
                                    <span className="text-[11px] font-semibold tabular-nums text-slate-700">{formatSignedPct(item.revenue_uplift_pct, 1)}</span>
                                  </div>
                                  <div className="flex flex-col items-center">
                                    <div className="relative h-32 w-full">
                                      <div className={`absolute bottom-0 left-[12%] w-[76%] rounded-t-md ${budColor}`} style={{ height: `${budBarH <= 0 ? 0 : Math.max(2, budBarH)}%` }} />
                                    </div>
                                    <span className="mt-3 text-center text-[10px] font-bold uppercase tracking-[0.08em] text-slate-400">Budget Used</span>
                                    <span className="mt-0.5 text-[12px] font-semibold tabular-nums text-slate-800">{formatMetric(budgetPct, 0)}%</span>
                                  </div>
                                </div>
                              </button>
                            )
                          })}
                        </div>
                        </div>

                        {/* Pagination */}
                        <div className="flex items-center justify-between gap-3">
                          <p className="text-xs text-slate-500">
                            Page {Math.max(1, scenarioResults!.pagination.page)} of {Math.max(1, scenarioResults!.pagination.total_pages)} · {scenarioResults!.pagination.total_count.toLocaleString()} total
                          </p>
                          <div className="flex gap-2">
                            <button
                              type="button"
                              onClick={() => setScenarioPage((prev) => Math.max(1, prev - 1))}
                              disabled={scenarioResults!.pagination.page <= 1}
                              className="rounded-full border border-slate-300 bg-white px-4 py-1.5 text-xs font-semibold text-slate-600 transition hover:border-slate-400 disabled:cursor-not-allowed disabled:opacity-40"
                            >
                              Previous
                            </button>
                            <button
                              type="button"
                              onClick={() => setScenarioPage((prev) => Math.min(Math.max(1, scenarioResults!.pagination.total_pages), prev + 1))}
                              disabled={scenarioResults!.pagination.page >= Math.max(1, scenarioResults!.pagination.total_pages)}
                              className="rounded-full border border-slate-300 bg-white px-4 py-1.5 text-xs font-semibold text-slate-600 transition hover:border-slate-400 disabled:cursor-not-allowed disabled:opacity-40"
                            >
                              Next
                            </button>
                          </div>
                        </div>
                      </div>
                    )}
                  </div>
                  )}
                  </div>
                </>
              )}

              </div>
              )}
            </div>
          )}

        </div>
      </div>

      {allRevealed && hitlMode === 'approved' && (
        <div className="overflow-hidden rounded-[28px] border border-[#d8c8ae] bg-white shadow-[0_20px_60px_rgba(123,92,51,0.12)]">
          <div className="flex items-center justify-between gap-3 px-5 py-5">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.16em] text-[#8c7554]">Scenario Generation</p>
              <p className="mt-1 text-sm text-slate-600">Generate and review scenario options separately from Trinity analysis.</p>
            </div>
            <button
              type="button"
              onClick={() => setScenarioSectionCollapsed((prev) => !prev)}
              className="rounded-full border border-[#d7cbb7] bg-white px-2.5 py-1 text-[11px] font-semibold text-slate-600 transition hover:border-[#9c7a4a] hover:text-[#7b5c33]"
            >
              {scenarioSectionCollapsed ? 'Expand ▼' : 'Collapse ▲'}
            </button>
          </div>

          {!scenarioSectionCollapsed && (
            <div className="border-t border-slate-100 px-5 py-5">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <p className="text-xs font-semibold uppercase tracking-[0.16em] text-[#8c7554]">Generated Scenarios</p>
                  <p className="mt-1 text-sm text-slate-600">5,000 scenarios generated from the approved market plan.</p>
                </div>
                {scenarioHandoff && !scenarioResults && (
                  <button
                    type="button"
                    onClick={() => { void startScenarioGeneration() }}
                    disabled={scenarioGenerationActive}
                    className="rounded-full bg-[#7b5c33] px-4 py-2 text-sm font-semibold text-white transition hover:bg-[#6c4f2a] disabled:cursor-not-allowed disabled:bg-slate-300"
                  >
                    {scenarioGenerationActive ? 'Generating…' : 'Generate 5,000 Scenarios →'}
                  </button>
                )}
              </div>

              {scenarioHandoffLoading && (
                <div className="mt-4 flex items-center gap-3 rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3">
                  <span className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-slate-300 border-t-[#7b5c33]" />
                  <p className="text-sm font-semibold text-slate-700">Preparing generation plan…</p>
                </div>
              )}

              {scenarioHandoffError ? <p className="mt-4 rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-600">{scenarioHandoffError}</p> : null}

              {scenarioHandoff && !scenarioResults && !scenarioGenerationActive && (
                <div className="mt-4 grid gap-3 lg:grid-cols-3">
                  <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-4">
                    <p className="text-xs font-bold uppercase tracking-[0.12em] text-slate-500">Target Budget</p>
                    <p className="mt-2 text-xl font-semibold text-slate-900">{formatBudgetValue(scenarioHandoff!.budget_context.target_budget)}</p>
                  </div>
                  <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-4">
                    <p className="text-xs font-bold uppercase tracking-[0.12em] text-slate-500">Scenario Envelope</p>
                    <p className="mt-1 text-sm font-semibold text-slate-900">{formatBudgetValue(scenarioHandoff!.budget_context.scenario_budget_lower)} – {formatBudgetValue(scenarioHandoff!.budget_context.scenario_budget_upper)}</p>
                    <p className="mt-1 text-xs text-slate-500">{formatMetric(scenarioHandoff!.budget_context.scenario_range_lower_pct, 0)}% – {formatMetric(scenarioHandoff!.budget_context.scenario_range_upper_pct, 0)}%</p>
                  </div>
                  <div className="rounded-2xl border border-emerald-200 bg-emerald-50 px-4 py-4">
                    <p className="text-xs font-bold uppercase tracking-[0.12em] text-emerald-700">Market Actions</p>
                    <p className="mt-2 text-sm font-semibold text-emerald-800">{handoffIncreaseMarkets.length} increase · {handoffDecreaseMarkets.length} decrease · {handoffHoldMarkets.length} hold</p>
                  </div>
                </div>
              )}

              {scenarioGenerationActive && (
                <div className="mt-4 rounded-2xl border border-slate-200 bg-white px-4 py-4">
                  <div className="flex items-center justify-between gap-3">
                    <p className="text-sm font-semibold text-slate-800">{scenarioMessage || 'Running scenario generation...'}</p>
                    <span className="text-sm font-semibold text-slate-500">{Math.round(scenarioProgress)}%</span>
                  </div>
                  <div className="mt-3 h-2 w-full rounded-full bg-slate-100">
                    <div className="h-2 rounded-full bg-[#7b5c33] transition-all" style={{ width: `${Math.max(4, scenarioProgress)}%` }} />
                  </div>
                </div>
              )}

              {scenarioError ? <p className="mt-4 rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-600">{scenarioError}</p> : null}

              {scenarioResults && (
                <>
                <div className="mt-4 space-y-4">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="rounded-full bg-emerald-50 px-3 py-1.5 text-[11px] font-semibold text-emerald-700">{scenarioResults!.summary.scenario_count.toLocaleString()} scenarios</span>
                    <span className="rounded-full bg-slate-100 px-3 py-1 text-[11px] font-semibold text-slate-600">Budget {formatBudgetValue(scenarioResults!.summary.target_budget)}</span>
                    <span className="rounded-full bg-slate-100 px-3 py-1 text-[11px] font-semibold text-slate-600">{scenarioResults!.summary.selected_markets.length} markets</span>
                    <button
                      type="button"
                      onClick={() => { void startScenarioGeneration() }}
                      className="ml-auto rounded-full border border-[#d7cbb7] bg-white px-3 py-1 text-xs font-semibold text-slate-600 transition hover:border-[#9c7a4a] hover:text-[#7b5c33]"
                    >
                      Regenerate
                    </button>
                  </div>

                  <div ref={reachFiltersRef} className="grid gap-3 rounded-2xl border border-slate-200 bg-white px-4 py-4 lg:grid-cols-12">
                    <div className="lg:col-span-3">
                      <label className="text-xs font-semibold uppercase tracking-[0.12em] text-slate-500">Sort by</label>
                      <select value={scenarioSortKey} onChange={(e) => { setScenarioSortKey(e.target.value); setScenarioPage(1) }}
                        className="mt-1.5 w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm text-slate-700">
                        <option value="revenue_uplift_pct">Revenue uplift</option>
                        <option value="volume_uplift_pct">Volume uplift</option>
                        <option value="balanced_score">Balanced score</option>
                      </select>
                    </div>
                    <div className="lg:col-span-3">
                      <label className="text-xs font-semibold uppercase tracking-[0.12em] text-slate-500">Min Volume Uplift %</label>
                      <input type="number" step="0.01" value={scenarioMinVolumePct}
                        onChange={(e) => { setScenarioMinVolumePct(e.target.value); setScenarioPage(1) }}
                        className="mt-1.5 w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm text-slate-700"
                        placeholder="e.g. 2.0" />
                    </div>
                    <div className="lg:col-span-3">
                      <label className="text-xs font-semibold uppercase tracking-[0.12em] text-slate-500">Min Revenue Uplift %</label>
                      <input type="number" step="0.01" value={scenarioMinRevenuePct}
                        onChange={(e) => { setScenarioMinRevenuePct(e.target.value); setScenarioPage(1) }}
                        className="mt-1.5 w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm text-slate-700"
                        placeholder="e.g. 2.5" />
                    </div>
                    <div className="lg:col-span-3">
                      <label className="text-xs font-semibold uppercase tracking-[0.12em] text-slate-500">Max Budget Utilized %</label>
                      <input type="number" step="0.01" value={scenarioMaxBudgetUtilizedPctFilter}
                        onChange={(e) => { setScenarioMaxBudgetUtilizedPctFilter(e.target.value); setScenarioPage(1) }}
                        className="mt-1.5 w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm text-slate-700"
                        placeholder="e.g. 100" />
                    </div>
                    {scenarioReachFilters.map((filter, index) => {
                      const otherFilter = scenarioReachFilters[index === 0 ? 1 : 0]
                      const availableMarkets = (scenarioResults?.summary.selected_markets ?? markets).filter(
                        (m) => !otherFilter.markets.includes(m)
                      )
                      return (
                      <div key={`reach-filter-${index}`} className="relative rounded-2xl border border-slate-200 bg-slate-50 px-3 py-3 lg:col-span-6">
                        <div className="flex items-center justify-between gap-2">
                          <label className="text-xs font-semibold uppercase tracking-[0.12em] text-slate-500">
                            Reach Share Filter {index + 1}
                          </label>
                          {filter.markets.length ? (
                            <span className="rounded-full bg-white px-2.5 py-1 text-[10px] font-semibold text-slate-600">
                              {filter.markets.length} selected
                            </span>
                          ) : null}
                        </div>
                        <button
                          type="button"
                          onClick={() => setOpenReachFilterIndex((prev) => (prev === index ? null : index))}
                          className="mt-3 flex w-full items-center justify-between rounded-2xl border border-slate-300 bg-white px-3 py-2.5 text-left text-sm text-slate-700 shadow-sm transition hover:border-[#9c7a4a]"
                        >
                          <span className="truncate pr-3">
                            {filter.markets.length > 0 ? `${filter.markets.length} market${filter.markets.length !== 1 ? 's' : ''} selected` : 'Select markets'}
                          </span>
                          <span className="text-xs text-slate-400">{openReachFilterIndex === index ? '▲' : '▼'}</span>
                        </button>
                        {openReachFilterIndex === index ? (
                          <div className="absolute left-3 right-3 top-[5.5rem] z-20 rounded-2xl border border-slate-200 bg-white p-2 shadow-xl">
                            <div className="max-h-56 space-y-1 overflow-y-auto pr-1">
                              {availableMarkets.map((market) => {
                                const selected = filter.markets.includes(market)
                                return (
                                  <label
                                    key={`reach-filter-${index}-${market}`}
                                    className={`flex cursor-pointer items-center gap-3 rounded-xl px-3 py-2 text-sm transition ${selected ? 'bg-[#f4ece0] text-[#7b5c33]' : 'hover:bg-slate-50 text-slate-700'}`}
                                  >
                                    <input
                                      type="checkbox"
                                      checked={selected}
                                      onChange={(e) => {
                                        const nextMarkets = e.target.checked
                                          ? [...filter.markets, market]
                                          : filter.markets.filter((item) => item !== market)
                                        setScenarioReachFilter(index, { markets: nextMarkets })
                                      }}
                                      className="h-4 w-4 rounded border-slate-300 text-[#7b5c33] focus:ring-[#c9b79b]"
                                    />
                                    <span className="flex-1">{market}</span>
                                  </label>
                                )
                              })}
                            </div>
                            <div className="mt-2 flex items-center justify-between gap-2 border-t border-slate-100 px-2 pt-2">
                              <button
                                type="button"
                                onClick={() => setScenarioReachFilter(index, { markets: [] })}
                                className="text-xs font-semibold text-slate-500 transition hover:text-rose-600"
                              >
                                Clear
                              </button>
                              <button
                                type="button"
                                onClick={() => setOpenReachFilterIndex(null)}
                                className="rounded-full bg-[#7b5c33] px-3 py-1 text-xs font-semibold text-white transition hover:bg-[#6c4f2a]"
                              >
                                Done
                              </button>
                            </div>
                          </div>
                        ) : null}
                        <select
                          value={filter.direction}
                          onChange={(e) => setScenarioReachFilter(index, { direction: e.target.value as 'higher' | 'lower' })}
                          disabled={!filter.markets.length}
                          className="mt-3 w-full rounded-2xl border border-slate-300 bg-white px-3 py-2 text-sm font-medium text-slate-700 shadow-sm disabled:bg-slate-100 disabled:text-slate-400"
                        >
                          <option value="higher">Higher than last year</option>
                          <option value="lower">Lower than last year</option>
                        </select>
                      </div>
                      )
                    })}
                  </div>

                  <div className="px-1 py-2">
                    <div className="flex flex-wrap items-center justify-between gap-3">
                      <div>
                        <p className="text-sm font-semibold text-slate-900">Scenario Comparison</p>
                        <p className="mt-1 text-xs text-slate-500">Showing 5 scenarios at a time with grouped bars for volume, revenue, and budget utilised.</p>
                      </div>
                      <p className="text-[10px] text-slate-400">Click any scenario to see per-market budget breakdown.</p>
                    </div>
                    <div className="mt-5 grid gap-4 lg:grid-cols-5">
                    {scenarioResults!.items.map((item) => {
                      const budgetPct = scenarioBudgetUtilizedPct(item)
                      const volBarH = Math.max(0, Math.min(100, Math.abs(item.volume_uplift_pct) * 6.5))
                      const revBarH = Math.max(0, Math.min(100, Math.abs(item.revenue_uplift_pct) * 6.5))
                      const budBarH = Math.max(0, Math.min(100, ((budgetPct - 80) / 40) * 100))
                      const volColor = item.volume_uplift_pct >= 0 ? 'bg-emerald-500' : 'bg-rose-400'
                      const revColor = item.revenue_uplift_pct >= 0 ? 'bg-blue-500' : 'bg-rose-400'
                      const budColor = budgetPct > 100 ? 'bg-rose-400' : budgetPct > 90 ? 'bg-amber-400' : 'bg-slate-400'
                      return (
                        <div
                          key={item.scenario_id}
                          className="flex flex-col rounded-2xl border border-slate-200 bg-white transition hover:border-[#9c7a4a] hover:shadow-md"
                        >
                          <button
                            type="button"
                            onClick={() => {
                              setScenarioModal(item)
                              setScenarioModalSplitView('reach')
                              setScenarioModalSortBy('budget_delta')
                              setScenarioModalChangeFilter('all')
                              setScenarioPlanMessage('')
                            }}
                            className="flex-1 px-4 pt-4 pb-2 text-left"
                          >
                            <div className="mb-4">
                              <div className="flex items-center justify-between gap-2">
                                <p className="text-sm font-semibold text-slate-900">{scenarioDisplayName(item)}</p>
                                <span className="rounded-full bg-slate-200 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-[0.08em] text-slate-600">{item.family}</span>
                              </div>
                            </div>
                            <div className="relative grid h-44 grid-cols-3 gap-4">
                              <div className="pointer-events-none absolute inset-x-0 bottom-9 border-t border-slate-200" />
                              <div className="flex flex-col items-center">
                                <div className="relative h-32 w-full">
                                  <div className={`absolute bottom-0 left-[12%] w-[76%] rounded-t-md ${volColor}`} style={{ height: `${volBarH <= 0 ? 0 : Math.max(8, volBarH)}%` }} />
                                </div>
                                <span className="mt-3 text-[10px] font-bold uppercase tracking-wider text-slate-400">Volume</span>
                                <span className="text-[11px] font-semibold tabular-nums text-slate-700">{formatSignedPct(item.volume_uplift_pct, 1)}</span>
                              </div>
                              <div className="flex flex-col items-center">
                                <div className="relative h-32 w-full">
                                  <div className={`absolute bottom-0 left-[12%] w-[76%] rounded-t-md ${revColor}`} style={{ height: `${revBarH <= 0 ? 0 : Math.max(8, revBarH)}%` }} />
                                </div>
                                <span className="mt-3 text-[10px] font-bold uppercase tracking-wider text-slate-400">Revenue</span>
                                <span className="text-[11px] font-semibold tabular-nums text-slate-700">{formatSignedPct(item.revenue_uplift_pct, 1)}</span>
                              </div>
                              <div className="flex flex-col items-center">
                                <div className="relative h-32 w-full">
                                  <div className={`absolute bottom-0 left-[12%] w-[76%] rounded-t-md ${budColor}`} style={{ height: `${budBarH <= 0 ? 0 : Math.max(2, budBarH)}%` }} />
                                </div>
                                <span className="mt-3 text-center text-[10px] font-bold uppercase tracking-[0.08em] text-slate-400">Budget Used</span>
                                <span className="mt-0.5 text-[12px] font-semibold tabular-nums text-slate-800">{formatMetric(budgetPct, 0)}%</span>
                              </div>
                            </div>
                          </button>
                          <div className="border-t border-slate-100 px-4 py-2">
                            <button
                              type="button"
                              onClick={() => openZoomModal(item)}
                              className="w-full rounded-full bg-[#f5ede0] py-1 text-[11px] font-semibold text-[#7b5c33] transition hover:bg-[#ede0cc] disabled:cursor-not-allowed disabled:opacity-50"
                            >
                              Generate 1,000 near this →
                            </button>
                          </div>
                        </div>
                      )
                    })}
                  </div>
                  </div>

                  <div className="flex items-center justify-between gap-3">
                    <p className="text-xs text-slate-500">
                      Page {Math.max(1, scenarioResults!.pagination.page)} of {Math.max(1, scenarioResults!.pagination.total_pages)} · {scenarioResults!.pagination.total_count.toLocaleString()} total
                    </p>
                    <div className="flex gap-2">
                      <button
                        type="button"
                        onClick={() => setScenarioPage((prev) => Math.max(1, prev - 1))}
                        disabled={scenarioResults!.pagination.page <= 1}
                        className="rounded-full border border-slate-300 bg-white px-4 py-1.5 text-xs font-semibold text-slate-600 transition hover:border-slate-400 disabled:cursor-not-allowed disabled:opacity-40"
                      >
                        Previous
                      </button>
                      <button
                        type="button"
                        onClick={() => setScenarioPage((prev) => Math.min(Math.max(1, scenarioResults!.pagination.total_pages), prev + 1))}
                        disabled={scenarioResults!.pagination.page >= Math.max(1, scenarioResults!.pagination.total_pages)}
                        className="rounded-full border border-slate-300 bg-white px-4 py-1.5 text-xs font-semibold text-slate-600 transition hover:border-slate-400 disabled:cursor-not-allowed disabled:opacity-40"
                      >
                        Next
                      </button>
                    </div>
                  </div>
                </div>

                {/* Zoom config strip — always shown when results are loaded */}
                <div className="hidden mt-6 rounded-2xl border border-[#ede4d6] bg-[#fdf8f2] px-5 py-4">
                  <p className="mb-3 text-[11px] font-bold uppercase tracking-widest text-[#7b5c33]">Explore Near a Scenario</p>
                  <div className="flex flex-wrap items-end gap-4">
                    <div>
                      <label className="mb-1 block text-[11px] font-semibold text-slate-500">Band (±%)</label>
                      <input
                        type="number"
                        min={1}
                        max={50}
                        value={zoomBandPct}
                        onChange={(e) => setZoomBandPct(Math.max(1, Math.min(50, Number(e.target.value))))}
                        className="w-20 rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-sm text-slate-800 focus:outline-none focus:ring-2 focus:ring-[#9c7a4a]/40"
                      />
                    </div>
                    <div className="flex-1">
                      <label className="mb-1 block text-[11px] font-semibold text-slate-500">Additional prompt (optional — uses AI to adjust strategy)</label>
                      <input
                        type="text"
                        placeholder="e.g. favour markets with higher reach share growth"
                        value={zoomPrompt}
                        onChange={(e) => setZoomPrompt(e.target.value)}
                        className="w-full rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-sm text-slate-800 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-[#9c7a4a]/40"
                      />
                    </div>
                  </div>
                  <p className="mt-2 text-[11px] text-slate-400">Click <span className="font-semibold text-[#7b5c33]">Explore 1,000 near this →</span> on any scenario card above to generate 1,000 scenarios tightly clustered around that plan's total budget.</p>
                </div>

              {/* Zoom results */}
              {false && zoomAnchor && (zoomLoading || zoomStatus !== 'idle') && (
                <div className="mt-6 rounded-2xl border border-slate-200 bg-white px-5 py-5">
                  <div className="mb-4 flex items-center justify-between gap-3">
                    <div>
                      <p className="text-sm font-semibold text-slate-900">Zoom: 1,000 scenarios near {scenarioDisplayName(zoomAnchor!)}</p>
                      <p className="mt-0.5 text-xs text-slate-500">Budget band ±{zoomBandPct}% around {scenarioDisplayName(zoomAnchor!)}'s total spend{zoomPrompt.trim() ? ' · with AI prompt refinement' : ''}</p>
                    </div>
                    <button
                      type="button"
                      onClick={() => { setZoomAnchor(null); setZoomStatus('idle'); setZoomResults(null); setZoomError(''); setZoomJobId('') }}
                      className="rounded-full border border-slate-200 bg-white px-3 py-1 text-xs font-semibold text-slate-500 transition hover:border-slate-400"
                    >
                      Clear
                    </button>
                  </div>

                  {zoomError && (
                    <p className="rounded-lg bg-rose-50 px-4 py-3 text-sm text-rose-600">{zoomError}</p>
                  )}

                  {(zoomStatus === 'queued' || zoomStatus === 'running') && !zoomError && (
                    <div className="flex items-center gap-3 py-4">
                      <div className="h-5 w-5 animate-spin rounded-full border-2 border-[#9c7a4a] border-t-transparent" />
                      <p className="text-sm text-slate-500">{zoomMessage || 'Generating zoom scenarios…'} {zoomProgress > 0 && `(${Math.round(zoomProgress)}%)`}</p>
                    </div>
                  )}

                  {zoomStatus === 'completed' && zoomResults && (
                    <>
                      <div className="mb-4 flex items-center justify-between">
                        <p className="text-xs text-slate-500">{zoomResults!.pagination.total_count.toLocaleString()} zoom scenarios · click any card for market breakdown</p>
                      </div>
                      <div className="grid gap-4 lg:grid-cols-5">
                        {zoomResults!.items.map((item) => {
                          const zBudgetPct = scenarioBudgetUtilizedPct(item)
                          const zVolH = Math.max(0, Math.min(100, Math.abs(item.volume_uplift_pct) * 6.5))
                          const zRevH = Math.max(0, Math.min(100, Math.abs(item.revenue_uplift_pct) * 6.5))
                          const zBudH = Math.max(0, Math.min(100, ((zBudgetPct - 80) / 40) * 100))
                          const zVol = item.volume_uplift_pct >= 0 ? 'bg-emerald-500' : 'bg-rose-400'
                          const zRev = item.revenue_uplift_pct >= 0 ? 'bg-blue-500' : 'bg-rose-400'
                          const zBud = zBudgetPct > 100 ? 'bg-rose-400' : zBudgetPct > 90 ? 'bg-amber-400' : 'bg-slate-400'
                          return (
                            <button
                              key={item.scenario_id}
                              type="button"
                              onClick={() => { setScenarioModal(item); setScenarioModalSplitView('reach'); setScenarioModalSortBy('budget_delta'); setScenarioModalChangeFilter('all'); setScenarioPlanMessage('') }}
                              className="rounded-2xl border border-slate-200 bg-white px-4 py-4 text-left transition hover:border-[#9c7a4a] hover:shadow-md"
                            >
                              <div className="mb-4 flex items-center justify-between gap-2">
                                <p className="text-sm font-semibold text-slate-900">{scenarioDisplayName(item)}</p>
                                <span className="rounded-full bg-[#f5ede0] px-2 py-0.5 text-[10px] font-semibold uppercase tracking-[0.08em] text-[#7b5c33]">{item.family}</span>
                              </div>
                              <div className="relative grid h-44 grid-cols-3 gap-4">
                                <div className="pointer-events-none absolute inset-x-0 bottom-9 border-t border-slate-200" />
                                <div className="flex flex-col items-center">
                                  <div className="relative h-32 w-full">
                                    <div className={`absolute bottom-0 left-[12%] w-[76%] rounded-t-md ${zVol}`} style={{ height: `${zVolH <= 0 ? 0 : Math.max(8, zVolH)}%` }} />
                                  </div>
                                  <span className="mt-3 text-[10px] font-bold uppercase tracking-wider text-slate-400">Volume</span>
                                  <span className="text-[11px] font-semibold text-slate-700">{formatSignedPct(item.volume_uplift_pct, 1)}</span>
                                </div>
                                <div className="flex flex-col items-center">
                                  <div className="relative h-32 w-full">
                                    <div className={`absolute bottom-0 left-[12%] w-[76%] rounded-t-md ${zRev}`} style={{ height: `${zRevH <= 0 ? 0 : Math.max(8, zRevH)}%` }} />
                                  </div>
                                  <span className="mt-3 text-[10px] font-bold uppercase tracking-wider text-slate-400">Revenue</span>
                                  <span className="text-[11px] font-semibold text-slate-700">{formatSignedPct(item.revenue_uplift_pct, 1)}</span>
                                </div>
                                <div className="flex flex-col items-center">
                                  <div className="relative h-32 w-full">
                                    <div className={`absolute bottom-0 left-[12%] w-[76%] rounded-t-md ${zBud}`} style={{ height: `${zBudH <= 0 ? 0 : Math.max(2, zBudH)}%` }} />
                                  </div>
                                  <span className="mt-3 text-center text-[10px] font-bold uppercase tracking-[0.08em] text-slate-400">Budget Used</span>
                                  <span className="mt-0.5 text-[12px] font-semibold text-slate-800">{formatMetric(zBudgetPct, 0)}%</span>
                                </div>
                              </div>
                            </button>
                          )
                        })}
                      </div>
                      <div className="mt-4 flex items-center justify-between gap-3">
                        <p className="text-xs text-slate-500">Page {zoomResults!.pagination.page} of {Math.max(1, zoomResults!.pagination.total_pages)}</p>
                        <div className="flex gap-2">
                          <button type="button" onClick={() => setZoomPage((p) => Math.max(1, p - 1))} disabled={zoomResults!.pagination.page <= 1} className="rounded-full border border-slate-300 bg-white px-4 py-1.5 text-xs font-semibold text-slate-600 transition hover:border-slate-400 disabled:cursor-not-allowed disabled:opacity-40">Previous</button>
                          <button type="button" onClick={() => setZoomPage((p) => Math.min(Math.max(1, zoomResults!.pagination.total_pages), p + 1))} disabled={zoomResults!.pagination.page >= Math.max(1, zoomResults!.pagination.total_pages)} className="rounded-full border border-slate-300 bg-white px-4 py-1.5 text-xs font-semibold text-slate-600 transition hover:border-slate-400 disabled:cursor-not-allowed disabled:opacity-40">Next</button>
                        </div>
                      </div>
                    </>
                  )}
                </div>
              )}
              </>
            )}
            </div>
          )}
        </div>
      )}

      {zoomAnchor && (() => {
        const zoomBandLower = zoomAnchor.total_new_spend * (1 - zoomBandPct / 100)
        const zoomBandUpper = zoomAnchor.total_new_spend * (1 + zoomBandPct / 100)
        const zoomSelectedMarkets = zoomResults?.summary.selected_markets ?? scenarioResults?.summary.selected_markets ?? markets
        return (
          <div ref={zoomPanelRef} className="mt-6 rounded-[28px] border border-[#d8c8ae] bg-white shadow-[0_20px_60px_rgba(123,92,51,0.12)]">
            <div className="border-b border-slate-100 bg-white px-8 pb-5 pt-6">
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <div className="flex flex-wrap items-center gap-2">
                      <p className="text-lg font-bold text-slate-900">Generate 1,000 near {scenarioDisplayName(zoomAnchor)}</p>
                      <span className="rounded-full bg-[#f5ede0] px-2.5 py-0.5 text-[11px] font-semibold text-[#7b5c33]">{zoomAnchor.family}</span>
                    </div>
                    <p className="mt-2 text-sm text-slate-600">Set a tighter budget band, add an optional prompt refinement, then generate and filter the nearby scenario cluster below the 5,000-scenario section.</p>
                    <div className="mt-3 flex flex-wrap gap-2">
                      <span className="rounded-full bg-slate-100 px-2.5 py-1 text-[11px] font-semibold text-slate-600">Anchor spend {formatBudgetValue(zoomAnchor.total_new_spend)}</span>
                      <span className="rounded-full bg-emerald-50 px-2.5 py-1 text-[11px] font-semibold text-emerald-700">Vol {formatSignedPct(zoomAnchor.volume_uplift_pct, 2)}</span>
                      <span className="rounded-full bg-blue-50 px-2.5 py-1 text-[11px] font-semibold text-blue-700">Rev {formatSignedPct(zoomAnchor.revenue_uplift_pct, 2)}</span>
                    </div>
                    <p className="mt-3 text-xs text-slate-500">Select another scenario card above at any time to replace this unsaved 1,000-scenario run with a new anchor.</p>
                  </div>
                  <button
                    type="button"
                    onClick={() => closeZoomModal()}
                    className="rounded-full border border-slate-200 bg-white px-3 py-1.5 text-xs font-semibold text-slate-500 transition hover:border-slate-400 hover:text-slate-700"
                  >
                    Clear
                  </button>
                </div>
            </div>

            <div className="space-y-6 px-8 py-6">
                <div className="grid gap-4 xl:grid-cols-[minmax(0,1.6fr)_minmax(0,0.8fr)]">
                  <div className="rounded-3xl border border-slate-200 bg-[#fcfaf7] p-5">
                    <div className="grid gap-4 lg:grid-cols-[200px_minmax(0,1fr)]">
                      <div>
                        <label className="text-xs font-semibold uppercase tracking-[0.12em] text-slate-500">Band (+/- %)</label>
                        <input
                          type="number"
                          min={1}
                          max={50}
                          value={zoomBandPct}
                          onChange={(e) => setZoomBandPct(Math.max(1, Math.min(50, Number(e.target.value))))}
                          className="mt-1.5 w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm text-slate-700"
                        />
                        <p className="mt-2 text-xs text-slate-500">Budget range {formatBudgetValue(zoomBandLower)} to {formatBudgetValue(zoomBandUpper)}</p>
                      </div>
                      <div>
                        <label className="text-xs font-semibold uppercase tracking-[0.12em] text-slate-500">Additional Prompt</label>
                        <textarea
                          rows={3}
                          placeholder="e.g. favour markets with higher reach share growth"
                          value={zoomPrompt}
                          onChange={(e) => setZoomPrompt(e.target.value)}
                          className="mt-1.5 w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm text-slate-700 placeholder:text-slate-400"
                        />
                        <p className="mt-2 text-xs text-slate-500">When provided, this prompt revises the approved strategy before generating the nearby 1,000 scenarios.</p>
                      </div>
                    </div>
                  </div>

                  <div className="rounded-3xl border border-[#e6dccd] bg-[#fdf8f2] p-5">
                    <p className="text-xs font-semibold uppercase tracking-[0.12em] text-[#8c7554]">Generation Scope</p>
                    <div className="mt-3 space-y-3">
                      <div className="rounded-2xl border border-white/80 bg-white px-4 py-3">
                        <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-500">Target</p>
                        <p className="mt-1 text-xl font-semibold text-slate-900">1,000 scenarios</p>
                      </div>
                      <div className="rounded-2xl border border-white/80 bg-white px-4 py-3">
                        <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-500">Selected Markets</p>
                        <p className="mt-1 text-sm font-semibold text-slate-900">{zoomSelectedMarkets.length}</p>
                      </div>
                    </div>
                    <button
                      type="button"
                      onClick={() => void startZoomGeneration(zoomAnchor)}
                      disabled={zoomGenerationActive}
                      className="mt-4 w-full rounded-full bg-[#7b5c33] px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-[#6c4f2a] disabled:cursor-not-allowed disabled:bg-slate-300"
                    >
                      {zoomGenerationActive ? 'Generating...' : 'Generate 1,000 scenarios'}
                    </button>
                  </div>
                </div>

                {zoomError ? (
                  <p className="rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-600">{zoomError}</p>
                ) : null}

                {zoomGenerationActive ? (
                  <div className="rounded-2xl border border-slate-200 bg-white px-4 py-4">
                    <div className="flex items-center justify-between gap-3">
                      <p className="text-sm font-semibold text-slate-800">{zoomMessage || 'Generating zoom scenarios...'}</p>
                      <span className="text-sm font-semibold text-slate-500">{Math.round(zoomProgress)}%</span>
                    </div>
                    <div className="mt-3 h-2 w-full rounded-full bg-slate-100">
                      <div className="h-2 rounded-full bg-[#7b5c33] transition-all" style={{ width: `${Math.max(4, zoomProgress)}%` }} />
                    </div>
                  </div>
                ) : null}

                {zoomResults ? (
                  <div className="space-y-4">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="rounded-full bg-emerald-50 px-3 py-1.5 text-[11px] font-semibold text-emerald-700">{zoomResults.summary.scenario_count.toLocaleString()} scenarios</span>
                      <span className="rounded-full bg-slate-100 px-3 py-1 text-[11px] font-semibold text-slate-600">Budget {formatBudgetValue(zoomResults.summary.target_budget)}</span>
                      <span className="rounded-full bg-slate-100 px-3 py-1 text-[11px] font-semibold text-slate-600">{zoomResults.summary.selected_markets.length} markets</span>
                    </div>

                    <div ref={zoomReachFiltersRef} className="grid gap-3 rounded-2xl border border-slate-200 bg-white px-4 py-4 lg:grid-cols-12">
                      <div className="lg:col-span-3">
                        <label className="text-xs font-semibold uppercase tracking-[0.12em] text-slate-500">Sort by</label>
                        <select
                          value={zoomSortKey}
                          onChange={(e) => { setZoomSortKey(e.target.value); setZoomPage(1) }}
                          className="mt-1.5 w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm text-slate-700"
                        >
                          <option value="balanced_score">Balanced score</option>
                          <option value="revenue_uplift_pct">Revenue uplift</option>
                          <option value="volume_uplift_pct">Volume uplift</option>
                        </select>
                      </div>
                      <div className="lg:col-span-3">
                        <label className="text-xs font-semibold uppercase tracking-[0.12em] text-slate-500">Min Volume Uplift %</label>
                        <input
                          type="number"
                          step="0.01"
                          value={zoomMinVolumePct}
                          onChange={(e) => { setZoomMinVolumePct(e.target.value); setZoomPage(1) }}
                          className="mt-1.5 w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm text-slate-700"
                          placeholder="e.g. 2.0"
                        />
                      </div>
                      <div className="lg:col-span-3">
                        <label className="text-xs font-semibold uppercase tracking-[0.12em] text-slate-500">Min Revenue Uplift %</label>
                        <input
                          type="number"
                          step="0.01"
                          value={zoomMinRevenuePct}
                          onChange={(e) => { setZoomMinRevenuePct(e.target.value); setZoomPage(1) }}
                          className="mt-1.5 w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm text-slate-700"
                          placeholder="e.g. 2.5"
                        />
                      </div>
                      <div className="lg:col-span-3">
                        <label className="text-xs font-semibold uppercase tracking-[0.12em] text-slate-500">Max Budget Utilized %</label>
                        <input
                          type="number"
                          step="0.01"
                          value={zoomMaxBudgetUtilizedPctFilter}
                          onChange={(e) => { setZoomMaxBudgetUtilizedPctFilter(e.target.value); setZoomPage(1) }}
                          className="mt-1.5 w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm text-slate-700"
                          placeholder="e.g. 100"
                        />
                      </div>
                      {zoomReachFilters.map((filter, index) => {
                        const otherFilter = zoomReachFilters[index === 0 ? 1 : 0]
                        const availableMarkets = zoomSelectedMarkets.filter((market) => !otherFilter.markets.includes(market))
                        return (
                          <div key={`zoom-reach-filter-${index}`} className="relative rounded-2xl border border-slate-200 bg-slate-50 px-3 py-3 lg:col-span-6">
                            <div className="flex items-center justify-between gap-2">
                              <label className="text-xs font-semibold uppercase tracking-[0.12em] text-slate-500">Reach Share Filter {index + 1}</label>
                              {filter.markets.length ? (
                                <span className="rounded-full bg-white px-2.5 py-1 text-[10px] font-semibold text-slate-600">{filter.markets.length} selected</span>
                              ) : null}
                            </div>
                            <button
                              type="button"
                              onClick={() => setOpenZoomReachFilterIndex((prev) => (prev === index ? null : index))}
                              className="mt-3 flex w-full items-center justify-between rounded-2xl border border-slate-300 bg-white px-3 py-2.5 text-left text-sm text-slate-700 shadow-sm transition hover:border-[#9c7a4a]"
                            >
                              <span className="truncate pr-3">
                                {filter.markets.length > 0 ? `${filter.markets.length} market${filter.markets.length !== 1 ? 's' : ''} selected` : 'Select markets'}
                              </span>
                              <span className="text-xs text-slate-400">{openZoomReachFilterIndex === index ? '^' : 'v'}</span>
                            </button>
                            {openZoomReachFilterIndex === index ? (
                              <div className="absolute left-3 right-3 top-[5.5rem] z-20 rounded-2xl border border-slate-200 bg-white p-2 shadow-xl">
                                <div className="max-h-56 space-y-1 overflow-y-auto pr-1">
                                  {availableMarkets.map((market) => {
                                    const selected = filter.markets.includes(market)
                                    return (
                                      <label
                                        key={`zoom-reach-filter-${index}-${market}`}
                                        className={`flex cursor-pointer items-center gap-3 rounded-xl px-3 py-2 text-sm transition ${selected ? 'bg-[#f4ece0] text-[#7b5c33]' : 'text-slate-700 hover:bg-slate-50'}`}
                                      >
                                        <input
                                          type="checkbox"
                                          checked={selected}
                                          onChange={(e) => {
                                            const nextMarkets = e.target.checked
                                              ? [...filter.markets, market]
                                              : filter.markets.filter((item) => item !== market)
                                            setZoomReachFilter(index, { markets: nextMarkets })
                                          }}
                                          className="h-4 w-4 rounded border-slate-300 text-[#7b5c33] focus:ring-[#9c7a4a]"
                                        />
                                        <span className="truncate">{market}</span>
                                      </label>
                                    )
                                  })}
                                </div>
                              </div>
                            ) : null}
                            <select
                              value={filter.direction}
                              onChange={(e) => setZoomReachFilter(index, { direction: e.target.value as 'higher' | 'lower' })}
                              disabled={!filter.markets.length}
                              className="mt-3 w-full rounded-2xl border border-slate-300 bg-white px-3 py-2 text-sm font-medium text-slate-700 shadow-sm disabled:bg-slate-100 disabled:text-slate-400"
                            >
                              <option value="higher">Higher than last year</option>
                              <option value="lower">Lower than last year</option>
                            </select>
                          </div>
                        )
                      })}
                    </div>

                    <div className="grid gap-4 lg:grid-cols-5">
                      {zoomResults.items.map((item) => {
                        const zBudgetPct = scenarioBudgetUtilizedPct(item)
                        const zVolH = Math.max(0, Math.min(100, Math.abs(item.volume_uplift_pct) * 6.5))
                        const zRevH = Math.max(0, Math.min(100, Math.abs(item.revenue_uplift_pct) * 6.5))
                        const zBudH = Math.max(0, Math.min(100, ((zBudgetPct - 80) / 40) * 100))
                        const zVol = item.volume_uplift_pct >= 0 ? 'bg-emerald-500' : 'bg-rose-400'
                        const zRev = item.revenue_uplift_pct >= 0 ? 'bg-blue-500' : 'bg-rose-400'
                        const zBud = zBudgetPct > 100 ? 'bg-rose-400' : zBudgetPct > 90 ? 'bg-amber-400' : 'bg-slate-400'
                        return (
                          <button
                            key={item.scenario_id}
                            type="button"
                            onClick={() => { setScenarioModal(item); setScenarioModalSplitView('reach'); setScenarioModalSortBy('budget_delta'); setScenarioModalChangeFilter('all'); setScenarioPlanMessage('') }}
                            className="rounded-2xl border border-slate-200 bg-white px-4 py-4 text-left transition hover:border-[#9c7a4a] hover:shadow-md"
                          >
                            <div className="mb-4 flex items-center justify-between gap-2">
                              <p className="text-sm font-semibold text-slate-900">{scenarioDisplayName(item)}</p>
                              <span className="rounded-full bg-[#f5ede0] px-2 py-0.5 text-[10px] font-semibold uppercase tracking-[0.08em] text-[#7b5c33]">{item.family}</span>
                            </div>
                            <div className="relative grid h-44 grid-cols-3 gap-4">
                              <div className="pointer-events-none absolute inset-x-0 bottom-9 border-t border-slate-200" />
                              <div className="flex flex-col items-center">
                                <div className="relative h-32 w-full">
                                  <div className={`absolute bottom-0 left-[12%] w-[76%] rounded-t-md ${zVol}`} style={{ height: `${zVolH <= 0 ? 0 : Math.max(8, zVolH)}%` }} />
                                </div>
                                <span className="mt-3 text-[10px] font-bold uppercase tracking-wider text-slate-400">Volume</span>
                                <span className="text-[11px] font-semibold text-slate-700">{formatSignedPct(item.volume_uplift_pct, 1)}</span>
                              </div>
                              <div className="flex flex-col items-center">
                                <div className="relative h-32 w-full">
                                  <div className={`absolute bottom-0 left-[12%] w-[76%] rounded-t-md ${zRev}`} style={{ height: `${zRevH <= 0 ? 0 : Math.max(8, zRevH)}%` }} />
                                </div>
                                <span className="mt-3 text-[10px] font-bold uppercase tracking-wider text-slate-400">Revenue</span>
                                <span className="text-[11px] font-semibold text-slate-700">{formatSignedPct(item.revenue_uplift_pct, 1)}</span>
                              </div>
                              <div className="flex flex-col items-center">
                                <div className="relative h-32 w-full">
                                  <div className={`absolute bottom-0 left-[12%] w-[76%] rounded-t-md ${zBud}`} style={{ height: `${zBudH <= 0 ? 0 : Math.max(2, zBudH)}%` }} />
                                </div>
                                <span className="mt-3 text-center text-[10px] font-bold uppercase tracking-[0.08em] text-slate-400">Budget Used</span>
                                <span className="mt-0.5 text-[12px] font-semibold text-slate-800">{formatMetric(zBudgetPct, 0)}%</span>
                              </div>
                            </div>
                          </button>
                        )
                      })}
                    </div>

                    <div className="flex items-center justify-between gap-3">
                      <p className="text-xs text-slate-500">Page {zoomResults.pagination.page} of {Math.max(1, zoomResults.pagination.total_pages)} · {zoomResults.pagination.total_count.toLocaleString()} total</p>
                      <div className="flex gap-2">
                        <button
                          type="button"
                          onClick={() => setZoomPage((p) => Math.max(1, p - 1))}
                          disabled={zoomResults.pagination.page <= 1}
                          className="rounded-full border border-slate-300 bg-white px-4 py-1.5 text-xs font-semibold text-slate-600 transition hover:border-slate-400 disabled:cursor-not-allowed disabled:opacity-40"
                        >
                          Previous
                        </button>
                        <button
                          type="button"
                          onClick={() => setZoomPage((p) => Math.min(Math.max(1, zoomResults.pagination.total_pages), p + 1))}
                          disabled={zoomResults.pagination.page >= Math.max(1, zoomResults.pagination.total_pages)}
                          className="rounded-full border border-slate-300 bg-white px-4 py-1.5 text-xs font-semibold text-slate-600 transition hover:border-slate-400 disabled:cursor-not-allowed disabled:opacity-40"
                        >
                          Next
                        </button>
                      </div>
                    </div>
                  </div>
                ) : !zoomGenerationActive ? (
                  <div className="rounded-2xl border border-dashed border-[#d7cbb7] bg-[#fcfaf7] px-5 py-8 text-center">
                    <p className="text-sm font-semibold text-slate-800">No nearby scenarios generated yet.</p>
                    <p className="mt-2 text-sm text-slate-500">Set the band and optional prompt above, then run the 1,000-scenario generation from this panel.</p>
                  </div>
                ) : null}
            </div>
          </div>
        )
      })()}

      {/* Scenario detail modal */}
      {scenarioModal && (() => {
        const budgetPct = scenarioBudgetUtilizedPct(scenarioModal)
        const rows = (scenarioModal.markets ?? []).slice().sort(
          (a, b) => (b.new_total_spend - b.old_total_spend) - (a.new_total_spend - a.old_total_spend)
        )
        const totalOldSpend = rows.reduce((sum, row) => sum + Math.max(0, Number(row.old_total_spend ?? 0)), 0)
        const splitRows = rows
          .map((row) => {
            const oldSpendSharePct = totalOldSpend > 0 ? (Math.max(0, Number(row.old_total_spend ?? 0)) / totalOldSpend) * 100 : 0
            const newSpendSharePct = Math.max(0, Number(row.new_budget_share ?? 0)) * 100
            const oldReachSharePct = Math.max(0, Number(row.fy25_reach_share_pct ?? 0))
            const newReachSharePct = Math.max(0, Number(row.new_reach_share_pct ?? 0))
            const oldSharePct = scenarioModalSplitView === 'reach' ? oldReachSharePct : oldSpendSharePct
            const newSharePct = scenarioModalSplitView === 'reach' ? newReachSharePct : newSpendSharePct
            return {
              ...row,
              oldSharePct,
              newSharePct,
              deltaSharePct: newSharePct - oldSharePct,
            }
          })
          .sort((a, b) => Math.abs(b.deltaSharePct) - Math.abs(a.deltaSharePct))
        const changedRows = rows
          .map((row) => {
            const splitRow = splitRows.find((item) => item.market === row.market)
            const marketMeta = modalMarketMeta.get(row.market)
            return {
              ...row,
              oldSharePct: splitRow?.oldSharePct ?? 0,
              newSharePct: splitRow?.newSharePct ?? 0,
              deltaSharePct: splitRow?.deltaSharePct ?? 0,
              deltaBudget: Number(row.new_total_spend ?? 0) - Number(row.old_total_spend ?? 0),
              brandSalience: marketMeta?.brandSalience ?? null,
              marketShareChange: marketMeta?.marketShareChange ?? null,
            }
          })
          .filter((row) => Math.abs(row.deltaBudget) > 0.01 || Math.abs(row.deltaSharePct) > 0.01)
        const filteredChangedRows = changedRows
          .filter((row) => {
            if (scenarioModalChangeFilter === 'increase') return row.deltaBudget > 0
            if (scenarioModalChangeFilter === 'decrease') return row.deltaBudget < 0
            return true
          })
          .sort((a, b) => {
            if (scenarioModalSortBy === 'brand_salience') {
              const left = Number(a.brandSalience ?? Number.NEGATIVE_INFINITY)
              const right = Number(b.brandSalience ?? Number.NEGATIVE_INFINITY)
              if (right !== left) return right - left
              return Math.abs(b.deltaBudget) - Math.abs(a.deltaBudget)
            }
            if (scenarioModalSortBy === 'market_share_change') {
              const left = Number(a.marketShareChange ?? Number.NEGATIVE_INFINITY)
              const right = Number(b.marketShareChange ?? Number.NEGATIVE_INFINITY)
              if (right !== left) return right - left
              return Math.abs(b.deltaBudget) - Math.abs(a.deltaBudget)
            }
            return Math.abs(b.deltaBudget) - Math.abs(a.deltaBudget)
          })
        const increaseCount = changedRows.filter((row) => row.deltaBudget > 0).length
        const decreaseCount = changedRows.filter((row) => row.deltaBudget < 0).length
        return (
          <div
            className="fixed inset-0 z-50 flex items-end justify-center bg-black/40 backdrop-blur-sm sm:items-center"
            onClick={() => {
              setScenarioModal(null)
              setScenarioPlanMessage('')
            }}
          >
            <div
              className="relative w-full max-w-[94rem] max-h-[94vh] overflow-y-auto rounded-t-3xl sm:rounded-3xl bg-white shadow-2xl"
              onClick={e => e.stopPropagation()}
            >
              {/* Header */}
              <div className="sticky top-0 z-10 bg-white px-8 pt-6 pb-5 border-b border-slate-100">
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <div className="flex items-center gap-2">
                      <p className="text-lg font-bold text-slate-900">{scenarioDisplayName(scenarioModal)}</p>
                      <span className="rounded-full bg-slate-100 px-2.5 py-0.5 text-[11px] font-semibold text-slate-600">{scenarioModal.family}</span>
                    </div>
                    <p className="mt-2 text-sm text-slate-600">
                      States changed in this scenario, with original and new split plus original and new budget.
                    </p>
                    <div className="mt-3 flex flex-wrap gap-2">
                      <span className="rounded-full bg-emerald-50 px-2.5 py-1 text-[11px] font-semibold text-emerald-700">Vol {formatSignedPct(scenarioModal.volume_uplift_pct, 2)}</span>
                      <span className="rounded-full bg-blue-50 px-2.5 py-1 text-[11px] font-semibold text-blue-700">Rev {formatSignedPct(scenarioModal.revenue_uplift_pct, 2)}</span>
                      <span className="rounded-full bg-slate-100 px-2.5 py-1 text-[11px] font-semibold text-slate-600">Budget used {formatMetric(budgetPct, 1)}%</span>
                    </div>
                    {scenarioPlanMessage ? (
                      <p className="mt-3 text-xs font-medium text-[#7b5c33]">{scenarioPlanMessage}</p>
                    ) : null}
                  </div>
                  <div className="flex shrink-0 items-center gap-2">
                    <button
                      type="button"
                      onClick={() => saveScenarioPlan(scenarioModal)}
                      className="rounded-full border border-slate-200 bg-white px-3 py-1.5 text-xs font-semibold text-slate-700 transition hover:border-[#9c7a4a] hover:text-[#7b5c33]"
                    >
                      Save Plan
                    </button>
                    <button
                      type="button"
                      onClick={() => editScenarioPlanFromModal()}
                      className="rounded-full border border-slate-200 bg-white px-3 py-1.5 text-xs font-semibold text-slate-700 transition hover:border-[#9c7a4a] hover:text-[#7b5c33]"
                    >
                      Edit Plan
                    </button>
                    <button
                      type="button"
                      onClick={() => downloadScenarioPlan(scenarioModal)}
                      className="rounded-full bg-[#7b5c33] px-3 py-1.5 text-xs font-semibold text-white transition hover:bg-[#6c4f2a]"
                    >
                      Download Plan
                    </button>
                    <button
                      type="button"
                      onClick={() => {
                        setScenarioModal(null)
                        setScenarioPlanMessage('')
                      }}
                      className="rounded-full border border-slate-200 bg-white p-2 text-slate-400 hover:text-slate-700"
                    >
                      x
                    </button>
                  </div>
                </div>
                <div className="mt-4 grid gap-3 xl:grid-cols-[minmax(0,1.1fr)_minmax(0,1.5fr)]">
                  <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3">
                    <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-500">Split View</p>
                    <div className="mt-2 inline-flex rounded-full border border-slate-200 bg-white p-1">
                      <button
                        type="button"
                        onClick={() => setScenarioModalSplitView('reach')}
                        className={`rounded-full px-3 py-1 text-xs font-semibold transition ${scenarioModalSplitView === 'reach' ? 'bg-[#7b5c33] text-white' : 'text-slate-600 hover:text-slate-900'}`}
                      >
                        Reach Split
                      </button>
                      <button
                        type="button"
                        onClick={() => setScenarioModalSplitView('spend')}
                        className={`rounded-full px-3 py-1 text-xs font-semibold transition ${scenarioModalSplitView === 'spend' ? 'bg-[#7b5c33] text-white' : 'text-slate-600 hover:text-slate-900'}`}
                      >
                        Spend Split
                      </button>
                    </div>
                  </div>
                  <div className="grid gap-3 sm:grid-cols-3">
                    <div className="rounded-2xl border border-emerald-200 bg-emerald-50 px-4 py-3">
                      <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-emerald-700">Budget Increased</p>
                      <p className="mt-2 text-2xl font-semibold text-emerald-900">{increaseCount}</p>
                    </div>
                    <div className="rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3">
                      <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-rose-700">Budget Decreased</p>
                      <p className="mt-2 text-2xl font-semibold text-rose-900">{decreaseCount}</p>
                    </div>
                    <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3">
                      <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-500">Changed States</p>
                      <p className="mt-2 text-2xl font-semibold text-slate-900">{changedRows.length}</p>
                    </div>
                  </div>
                </div>
              </div>

              <div className="px-8 py-6">
                <div className="rounded-2xl border border-slate-200 bg-white">
                  <div className="border-b border-slate-100 px-5 py-4">
                    <div className="flex flex-col gap-4 xl:flex-row xl:items-end xl:justify-between">
                      <div>
                        <p className="text-sm font-semibold text-slate-900">
                          {scenarioModalSplitView === 'reach' ? 'Changed States By Reach Split' : 'Changed States By Spend Split'}
                        </p>
                        <p className="mt-1 text-xs text-slate-500">Sort the changed states and focus only on the increases or decreases you want to inspect.</p>
                      </div>
                      <div className="grid gap-3 sm:grid-cols-2 xl:min-w-[30rem]">
                        <label className="rounded-2xl border border-slate-200 bg-slate-50 px-3 py-2">
                          <span className="text-[10px] font-semibold uppercase tracking-[0.12em] text-slate-500">Sort By</span>
                          <select
                            value={scenarioModalSortBy}
                            onChange={(e) => setScenarioModalSortBy(e.target.value as 'budget_delta' | 'brand_salience' | 'market_share_change')}
                            className="mt-1 block w-full bg-transparent text-sm font-medium text-slate-800 outline-none"
                          >
                            <option value="budget_delta">Budget change</option>
                            <option value="brand_salience">Brand salience</option>
                            <option value="market_share_change">Market share</option>
                          </select>
                        </label>
                        <label className="rounded-2xl border border-slate-200 bg-slate-50 px-3 py-2">
                          <span className="text-[10px] font-semibold uppercase tracking-[0.12em] text-slate-500">Show</span>
                          <select
                            value={scenarioModalChangeFilter}
                            onChange={(e) => setScenarioModalChangeFilter(e.target.value as 'all' | 'increase' | 'decrease')}
                            className="mt-1 block w-full bg-transparent text-sm font-medium text-slate-800 outline-none"
                          >
                            <option value="all">All changed states</option>
                            <option value="increase">Budget increased only</option>
                            <option value="decrease">Budget decreased only</option>
                          </select>
                        </label>
                      </div>
                    </div>
                  </div>
                  <div className="px-5 py-3">
                    <div className="grid grid-cols-[minmax(220px,1.4fr)_120px_120px_140px_140px] gap-3 border-b border-slate-100 pb-2 text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-400">
                      <span>Market</span>
                      <span>Original Split</span>
                      <span>New Split</span>
                      <span>Original Budget</span>
                      <span>New Budget</span>
                    </div>
                    <div className="max-h-[56vh] overflow-y-auto pr-1">
                    {filteredChangedRows.length > 0 ? filteredChangedRows.map((row) => {
                      const isIncrease = row.deltaBudget >= 0
                      const tone = isIncrease
                        ? {
                            rowBg: 'bg-emerald-50/60',
                            border: 'border-emerald-100',
                            pill: 'bg-emerald-100 text-emerald-800',
                            splitText: 'text-emerald-700',
                            budgetText: 'text-emerald-900',
                          }
                        : {
                            rowBg: 'bg-rose-50/60',
                            border: 'border-rose-100',
                            pill: 'bg-rose-100 text-rose-800',
                            splitText: 'text-rose-700',
                            budgetText: 'text-rose-900',
                          }
                      return (
                        <button
                          type="button"
                          key={`${row.market}-${scenarioModalSplitView}`}
                          onClick={() => setScenarioMarketDetailRow(row)}
                          className={`w-full grid grid-cols-[minmax(220px,1.4fr)_120px_120px_140px_140px] gap-3 border-b px-2 py-3 text-sm last:border-b-0 text-left transition hover:brightness-95 cursor-pointer ${tone.rowBg} ${tone.border}`}
                        >
                          <div>
                            <div className="flex flex-wrap items-center gap-2">
                              <p className="font-semibold text-slate-900">{row.market}</p>
                              <span className={`rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-[0.08em] ${tone.pill}`}>
                                {isIncrease ? 'Increased' : 'Decreased'}
                              </span>
                            </div>
                            <div className="mt-1 flex flex-wrap gap-2">
                              <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[10px] font-medium text-slate-600">
                                Salience {row.brandSalience != null ? formatMetric(row.brandSalience, 0) : 'n/a'}
                              </span>
                              <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[10px] font-medium text-slate-600">
                                Mkt share {row.marketShareChange != null ? formatSignedPct(row.marketShareChange, 1) : 'n/a'}
                              </span>
                            </div>
                          </div>
                          <div>
                            <p className="font-semibold tabular-nums text-slate-700">{formatMetric(row.oldSharePct, 2)}%</p>
                            <p className="mt-0.5 text-[10px] uppercase tracking-[0.08em] text-slate-400">Original</p>
                          </div>
                          <div>
                            <p className={`font-semibold tabular-nums ${tone.splitText}`}>{formatMetric(row.newSharePct, 2)}%</p>
                            <p className="mt-0.5 text-[10px] uppercase tracking-[0.08em] text-slate-400">New</p>
                          </div>
                          <div>
                            <p className="font-semibold tabular-nums text-slate-700">{formatCompactBudgetValue(row.old_total_spend)}</p>
                            <p className="mt-0.5 text-[10px] text-slate-400">{formatBudgetValue(row.old_total_spend)}</p>
                          </div>
                          <div>
                            <p className={`font-semibold tabular-nums ${tone.budgetText}`}>{formatCompactBudgetValue(row.new_total_spend)}</p>
                            <p className="mt-0.5 text-[10px] text-slate-400">{formatBudgetValue(row.new_total_spend)}</p>
                          </div>
                        </button>
                      )
                    }) : (
                      <div className="py-6 text-sm text-slate-500">No states match the current filter.</div>
                    )}
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )
      })()}

      {/* TV / Digital split detail sub-modal */}
      {scenarioMarketDetailRow && (() => {
        const r = scenarioMarketDetailRow
        const oldTvSpend = (Number(r.fy25_tv_reach ?? 0)) * (Number(r.tv_cpr ?? 0))
        const oldDigSpend = (Number(r.fy25_digital_reach ?? 0)) * (Number(r.digital_cpr ?? 0))
        const newTvSpend = Number(r.new_total_tv_spend ?? 0)
        const newDigSpend = Number(r.new_total_digital_spend ?? 0)
        const oldTotalForShare = oldTvSpend + oldDigSpend
        const newTotalForShare = newTvSpend + newDigSpend
        const oldTvSharePct = oldTotalForShare > 0 ? (oldTvSpend / oldTotalForShare) * 100 : 0
        const newTvSharePct = newTotalForShare > 0 ? (newTvSpend / newTotalForShare) * 100 : 0
        const tvDelta = newTvSpend - oldTvSpend
        const digDelta = newDigSpend - oldDigSpend
        const oldTvReachPct = Number(r.fy25_tv_share ?? 0) * 100
        const newTvReachPct = Number(r.tv_split ?? 0) * 100
        const oldDigReachPct = Number(r.fy25_digital_share ?? 0) * 100
        const newDigReachPct = Number(r.digital_split ?? 0) * 100
        const isIncrease = r.deltaBudget >= 0
        const signed = (v: number) => `${v >= 0 ? '+' : ''}${formatCompactBudgetValue(Math.abs(v))}`
        const deltaColor = (v: number) => v >= 0 ? 'text-emerald-700' : 'text-rose-700'
        const badgeBg = (v: number) => v >= 0 ? 'bg-emerald-100 text-emerald-700' : 'bg-rose-100 text-rose-700'
        return (
          <div
            className="fixed inset-0 z-[60] flex items-center justify-center bg-black/50 backdrop-blur-sm"
            onClick={() => setScenarioMarketDetailRow(null)}
          >
            <div
              className="w-full max-w-lg rounded-2xl border border-slate-200 bg-white shadow-2xl mx-4"
              onClick={e => e.stopPropagation()}
            >
              {/* Header */}
              <div className="flex items-center justify-between border-b border-slate-100 px-5 py-4">
                <div>
                  <p className="text-[10px] font-semibold uppercase tracking-wide text-slate-400">Market Detail</p>
                  <p className="mt-0.5 text-base font-bold text-slate-900">{r.market}</p>
                </div>
                <div className="flex items-center gap-2">
                  <span className={`rounded-full px-2.5 py-0.5 text-[10px] font-semibold uppercase ${isIncrease ? 'bg-emerald-100 text-emerald-700' : 'bg-rose-100 text-rose-700'}`}>
                    Budget {isIncrease ? 'Increased' : 'Decreased'}
                  </span>
                  <button
                    type="button"
                    onClick={() => setScenarioMarketDetailRow(null)}
                    className="rounded-lg border border-slate-200 bg-white p-1.5 text-slate-500 hover:bg-slate-50"
                  >
                    ✕
                  </button>
                </div>
              </div>

              <div className="space-y-4 p-5">
                {/* Total budget row */}
                <div className="grid grid-cols-3 gap-3">
                  <div className="rounded-xl border border-slate-200 bg-slate-50 p-3 text-center">
                    <p className="text-[10px] font-semibold uppercase tracking-wide text-slate-400">Original Budget</p>
                    <p className="mt-1 text-sm font-bold text-slate-700">{formatCompactBudgetValue(r.old_total_spend)}</p>
                    <p className="text-[10px] text-slate-400">{formatBudgetValue(r.old_total_spend)}</p>
                  </div>
                  <div className="rounded-xl border border-slate-200 bg-slate-50 p-3 text-center">
                    <p className="text-[10px] font-semibold uppercase tracking-wide text-slate-400">New Budget</p>
                    <p className={`mt-1 text-sm font-bold ${deltaColor(r.deltaBudget)}`}>{formatCompactBudgetValue(r.new_total_spend)}</p>
                    <p className="text-[10px] text-slate-400">{formatBudgetValue(r.new_total_spend)}</p>
                  </div>
                  <div className="rounded-xl border border-slate-200 bg-slate-50 p-3 text-center">
                    <p className="text-[10px] font-semibold uppercase tracking-wide text-slate-400">Change</p>
                    <p className={`mt-1 text-sm font-bold ${deltaColor(r.deltaBudget)}`}>{signed(r.deltaBudget)}</p>
                  </div>
                </div>

                {/* TV / Digital cards */}
                <div>
                  <p className="mb-2 text-[10px] font-semibold uppercase tracking-wide text-blue-600">TV vs Digital Budget Split</p>
                  <div className="grid grid-cols-2 gap-3">
                    {/* TV */}
                    <div className="rounded-xl border border-blue-100 bg-blue-50/40 p-3">
                      <div className="flex items-center justify-between">
                        <p className="text-xs font-bold text-blue-700">TV</p>
                        <span className={`rounded-full px-2 py-0.5 text-[10px] font-bold ${badgeBg(tvDelta)}`}>
                          {tvDelta !== 0 ? signed(tvDelta) : '—'}
                        </span>
                      </div>
                      <div className="mt-3 flex items-end gap-2">
                        <div className="flex-1 text-center">
                          <p className="text-[10px] uppercase tracking-wide text-slate-400">Before</p>
                          <p className="text-base font-bold text-slate-700">{formatCompactBudgetValue(oldTvSpend)}</p>
                          <p className="text-[10px] text-slate-500">{formatMetric(oldTvSharePct, 1)}% of market</p>
                        </div>
                        <p className="mb-1 text-slate-300">→</p>
                        <div className="flex-1 text-center">
                          <p className="text-[10px] uppercase tracking-wide text-slate-400">After</p>
                          <p className={`text-base font-bold ${deltaColor(tvDelta)}`}>{formatCompactBudgetValue(newTvSpend)}</p>
                          <p className="text-[10px] text-slate-500">{formatMetric(newTvSharePct, 1)}% of market</p>
                        </div>
                      </div>
                      {(oldTvReachPct > 0 || newTvReachPct > 0) && (
                        <p className="mt-2 text-[10px] text-slate-400">
                          Reach mix: {formatMetric(oldTvReachPct, 1)}% → <span className={deltaColor(newTvReachPct - oldTvReachPct)}>{formatMetric(newTvReachPct, 1)}%</span>
                        </p>
                      )}
                    </div>

                    {/* Digital */}
                    <div className="rounded-xl border border-purple-100 bg-purple-50/40 p-3">
                      <div className="flex items-center justify-between">
                        <p className="text-xs font-bold text-purple-700">Digital</p>
                        <span className={`rounded-full px-2 py-0.5 text-[10px] font-bold ${badgeBg(digDelta)}`}>
                          {digDelta !== 0 ? signed(digDelta) : '—'}
                        </span>
                      </div>
                      <div className="mt-3 flex items-end gap-2">
                        <div className="flex-1 text-center">
                          <p className="text-[10px] uppercase tracking-wide text-slate-400">Before</p>
                          <p className="text-base font-bold text-slate-700">{formatCompactBudgetValue(oldDigSpend)}</p>
                          <p className="text-[10px] text-slate-500">{formatMetric(100 - oldTvSharePct, 1)}% of market</p>
                        </div>
                        <p className="mb-1 text-slate-300">→</p>
                        <div className="flex-1 text-center">
                          <p className="text-[10px] uppercase tracking-wide text-slate-400">After</p>
                          <p className={`text-base font-bold ${deltaColor(digDelta)}`}>{formatCompactBudgetValue(newDigSpend)}</p>
                          <p className="text-[10px] text-slate-500">{formatMetric(100 - newTvSharePct, 1)}% of market</p>
                        </div>
                      </div>
                      {(oldDigReachPct > 0 || newDigReachPct > 0) && (
                        <p className="mt-2 text-[10px] text-slate-400">
                          Reach mix: {formatMetric(oldDigReachPct, 1)}% → <span className={deltaColor(newDigReachPct - oldDigReachPct)}>{formatMetric(newDigReachPct, 1)}%</span>
                        </p>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )
      })()}

      {/* Keyframe for step reveal animation */}
      <style>{`
        @keyframes fadeSlideIn {
          from { opacity: 0; transform: translateY(6px); }
          to   { opacity: 1; transform: translateY(0); }
        }
      `}</style>
    </div>
  )
}
