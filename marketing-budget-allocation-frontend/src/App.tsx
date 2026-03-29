import { useEffect, useMemo, useRef, useState } from 'react'
import type { FormEvent } from 'react'
import axios from 'axios'
import {
  Activity,
  BarChart3,
  Bot,
  ChevronDown,
  ChevronUp,
  CheckCircle2,
  LoaderCircle,
  ShieldCheck,
  SlidersHorizontal,
  Target,
  X,
} from 'lucide-react'

type AutoConfigResponse = {
  status: 'ok' | 'error'
  files: {
    model_data: string | null
    market_weights: string | null
    max_reach: string | null
  }
  brands: string[]
  markets_by_brand: Record<string, string[]>
  default_brand: string
  default_markets: string[]
}

type AllocationRow = {
  market: string
  new_budget_share: number
  tv_split: number
  digital_split: number
  tv_delta_reach_pct: number
  digital_delta_reach_pct: number
  tv_change_pct_var?: number
  digital_change_pct_var?: number
  new_annual_tv_reach?: number
  new_annual_digital_reach?: number
  fy25_tv_reach?: number
  fy25_digital_reach?: number
  new_tv_share?: number
  new_digital_share?: number
  fy25_tv_share?: number
  fy25_digital_share?: number
  max_annual_tv_reach?: number | null
  min_annual_tv_reach?: number | null
  max_annual_digital_reach?: number | null
  min_annual_digital_reach?: number | null
  max_tv_spend?: number | null
  min_tv_spend?: number | null
  max_digital_spend?: number | null
  min_digital_spend?: number | null
  tv_cpr?: number
  digital_cpr?: number
  new_total_tv_spend?: number
  new_total_digital_spend?: number
  old_total_spend?: number
  new_total_spend?: number
  pct_change_total_spend?: number
  total_fy_volume?: number
  prev_volume?: number
  new_volume?: number
  uplift_abs?: number
  uplift_pct?: number
  extra_budget_share?: number
}

type OptimizeAutoResponse = {
  status: 'ok' | 'error'
  message: string
  files: {
    model_data: string
    market_weights: string
    max_reach: string | null
  }
  selection: {
    brand: string
    markets: string[]
    budget_increase_type: 'percentage' | 'absolute'
    budget_increase_value: number
  }
  summary: {
    estimated_uplift_pct: number
    weighted_tv_share: number
    weighted_digital_share: number
    baseline_budget?: number
    optimized_budget?: number
    requested_target_budget?: number
    adjusted_target_budget?: number
    target_within_feasible?: boolean
    feasible_min_budget?: number
    feasible_max_budget?: number
    budget_constraint_value?: number
    total_new_spend?: number
    total_volume_uplift?: number
    total_volume_uplift_pct?: number
    solver_success?: boolean
    solver_message?: string
  }
  allocation_rows: AllocationRow[]
}

type BrandAllocationRow = {
  brand: string
  baseline_budget: number
  min_allowed_budget?: number
  max_allowed_budget?: number
  min_change_pct?: number
  max_change_pct?: number
  baseline_volume?: number
  avg_price_last_3_points?: number
  base_elasticity?: number
  halo_uplift?: number
  effective_elasticity?: number
  elasticity: number
  weight: number
  share: number
  allocated_budget: number
  uplift_amount: number
  estimated_new_volume?: number
  estimated_volume_uplift_abs?: number
  estimated_volume_uplift_pct?: number
  baseline_revenue?: number
  estimated_new_revenue?: number
  estimated_revenue_uplift_abs?: number
  estimated_revenue_uplift_pct?: number
}

type BrandAllocationResponse = {
  status: 'ok' | 'error'
  message: string
  files: {
    model_data: string
    national_learnings: string
  }
  selection: {
    budget_increase_type: 'percentage' | 'absolute'
    budget_increase_value: number
    selected_brands: string[]
  }
  summary: {
    baseline_total_budget: number
    requested_target_total_budget?: number
    target_total_budget: number
    incremental_budget: number
    feasible_min_total_budget?: number
    feasible_max_total_budget?: number
    baseline_total_revenue?: number
    estimated_total_new_revenue?: number
    estimated_total_revenue_uplift_abs?: number
    estimated_total_revenue_uplift_pct?: number
    baseline_total_volume?: number
    estimated_total_new_volume?: number
    estimated_total_volume_uplift_abs?: number
    estimated_total_volume_uplift_pct?: number
  }
  allocation_rows: BrandAllocationRow[]
}

type MarketOverride = {
  tv_cpr?: number
  digital_cpr?: number
  min_tv_spend?: number
  max_tv_spend?: number
  min_digital_spend?: number
  max_digital_spend?: number
}

type ScenarioJobCreateResponse = {
  job_id: string
  status: 'queued' | 'running' | 'completed' | 'failed' | 'expired'
  ready: boolean
  progress: number
  message: string
}

type ScenarioJobStatusResponse = {
  job_id: string
  ready: boolean
  status: 'queued' | 'running' | 'completed' | 'failed' | 'expired'
  progress: number
  message: string
  error_reason?: string | null
}

type ScenarioAnchor = {
  scenario_id: string
  family: string
  seed_source: string
  volume_uplift_pct: number
  revenue_uplift_pct: number
  volume_uplift_abs: number
  revenue_uplift_abs: number
  balanced_score: number
  weighted_tv_share: number
  weighted_digital_share: number
}

type ScenarioItem = {
  scenario_id: string
  scenario_index: number
  family: string
  seed_source: string
  volume_uplift_pct: number
  revenue_uplift_pct: number
  volume_uplift_abs: number
  revenue_uplift_abs: number
  balanced_score: number
  weighted_tv_share: number
  weighted_digital_share: number
  total_new_spend: number
  markets: AllocationRow[]
}

type ScenarioMarketFlowRow = {
  market: string
  old_budget_share_pct: number
  new_budget_share_pct: number
  budget_share_change_pct: number
  spend_delta_mn: number
  old_tv_split_pct: number
  new_tv_split_pct: number
  tv_split_change_pct: number
  old_digital_split_pct: number
  new_digital_split_pct: number
  digital_split_change_pct: number
}

type ScenarioResultsResponse = {
  ready: boolean
  job_id: string
  status: 'completed'
  summary: {
    scenario_count: number
    target_count: number
    requested_target_count?: number
    near_opt_count: number
    near_opt_target: number
    min_distance: number
    budget_tolerance: number
    runtime_seconds?: number
    runtime_cap_seconds?: number
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
  anchors: {
    best_volume: ScenarioAnchor | null
    best_revenue: ScenarioAnchor | null
    best_balanced: ScenarioAnchor | null
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

type SCurvePoint = {
  scale: number
  pct_change_input: number
  predicted_volume: number
  predicted_spend: number
  tv_reach?: number
  digital_reach?: number
  volume_uplift_abs: number
  volume_uplift_pct: number
  spend_change_pct: number
}

type SCurvesResponse = {
  status: 'ok' | 'error'
  message: string
  selection: {
    brand: string
    markets: string[]
  }
  summary: {
    baseline_volume: number
    baseline_spend: number
    baseline_tv_reach?: number
    baseline_digital_reach?: number
    tv_min_reach?: number
    tv_max_reach?: number
    digital_min_reach?: number
    digital_max_reach?: number
    points: number
    min_scale: number
    max_scale: number
  }
  equation_map?: {
    formula: string
    notes: string[]
    markets: Array<{
      market: string
      c: number
      beta_tv: number
      beta_digital: number
      carryover_tv: number
      carryover_digital: number
      midpoint_tv: number
      midpoint_digital: number
      mu_tv: number
      sigma_tv: number
      mu_digital: number
      sigma_digital: number
      min_tv: number
      max_tv: number
      min_digital: number
      max_digital: number
    }>
  }
  curves: {
    tv: SCurvePoint[]
    digital: SCurvePoint[]
  }
}

type ContributionItem = {
  variable: string
  label: string
  absolute_contribution: number
  share_pct: number
}

type ContributionResponse = {
  status: 'ok' | 'error'
  message: string
  selection: {
    brand: string
    market: string
    fiscal_year: string
  }
  summary: {
    prediction_total: number
    component_count: number
  }
  items: ContributionItem[]
}

type YoyGrowthItem = {
  fiscal_year: string
  volume_mn: number
  predicted_volume_mn?: number
  reach_mn: number
  yoy_growth_pct: number | null
  predicted_yoy_growth_pct?: number | null
}

type YoyGrowthResponse = {
  status: 'ok' | 'error'
  message: string
  selection: {
    brand: string
    market: string
  }
  summary: {
    latest_fiscal_year: string
    latest_volume_mn: number
    latest_reach_mn: number
    latest_yoy_growth_pct: number | null
    latest_predicted_volume_mn?: number
    latest_predicted_yoy_growth_pct?: number | null
    points: number
  }
  items: YoyGrowthItem[]
  waterfall?: {
    from_fiscal_year: string
    to_fiscal_year: string
    total_change_mn: number
    items: Array<{
      label: string
      delta_mn: number
      share_of_total_change_pct: number
    }>
  } | null
}

type AIInsightsStructuredAction = {
  state: string
  why: string
  action: string
}

type AIInsightsStructured = {
  headline?: string
  portfolio_takeaway?: string
  executive_summary: string
  portfolio_position: string
  state_clusters: {
    growth_leaders: string
    stable_core: string
    recovery_priority: string
  }
  where_to_increase: AIInsightsStructuredAction[]
  where_to_protect_reduce: AIInsightsStructuredAction[]
  channel_notes?: {
    tv?: string
    digital?: string
  }
  risks?: string[]
  evidence?: string[]
  summary_json?: AIInsightsSummaryJson
}

type AIInsightsSummaryJson = {
  headline: string
  portfolio_takeaway: string
  increase_markets: Array<{
    state: string
    channel: string
    reason: string
    action: string
  }>
  decrease_markets: Array<{
    state: string
    channel: string
    reason: string
    action: string
  }>
  channel_notes: {
    tv: string
    digital: string
  }
  risks: string[]
  evidence: string[]
}

type AIInsightsMarketCard = {
  market: string
  latest_fiscal_year: string
  latest_volume_mn: number
  latest_volume_lakh: number
  yoy_growth_pct: number
  tv_share_pct: number
  digital_share_pct: number
  tv_utilization_pct: number
  digital_utilization_pct: number
  tv_position_pct?: number
  digital_position_pct?: number
  tv_effectiveness_pct?: number
  digital_effectiveness_pct?: number
  tv_zone?: string
  digital_zone?: string
  category_salience_pct?: number
  brand_market_share_pct?: number
  leader_rank?: number
  leader_position?: string
  leader_brand?: string
  is_market_leader?: boolean
  media_responsiveness_pct?: number
  investment_quadrant?: string
  headroom_pct: number
  recommendation_action: string
}

type AIInsightsSignalSnapshot = {
  insights_brand: string
  insights_market: string
  yoy: {
    latest_fiscal_year: string
    latest_yoy_growth_pct: number
    latest_volume_mn: number
  }
  s_curve: {
    tv_points: number
    digital_points: number
    tv_first_uplift_pct: number
    tv_last_uplift_pct: number
    dg_first_uplift_pct: number
    dg_last_uplift_pct: number
  }
  contribution_top: Array<{
    variable: string
    abs: number
    share_pct: number
  }>
}

type AIInsightsPortfolioMetrics = {
  avg_yoy_growth_pct: number
  median_yoy_growth_pct: number
  positive_yoy_states: number
  negative_yoy_states: number
  median_headroom_pct: number
  avg_tv_effectiveness_pct: number
  avg_digital_effectiveness_pct: number
  tv_effective_states: number
  digital_effective_states: number
  avg_category_salience_pct: number
  market_leader_states: number
  top_opportunity_states: string[]
  top_risk_states: string[]
}

type AIInsightsSummaryResponse = {
  status: 'ok' | 'error'
  message: string
  selection: {
    brand: string
    markets: string[]
    markets_count: number
  }
  summary: {
    provider: string
    leaders_count: number
    core_count: number
    recovery_count: number
  }
  analysis_basis?: {
    primary_metric: string
    channel_logic: string
  }
  computed_executive_summary?: string
  channel_diagnostics?: {
    tv: {
      working_states: string[]
      attention_states: string[]
    }
    digital: {
      working_states: string[]
      attention_states: string[]
    }
  }
  state_clusters: {
    growth_leaders: string[]
    stable_core: string[]
    recovery_priority: string[]
  }
  investment_framework?: {
    salience_threshold_pct: number
    responsiveness_threshold_pct: number
    quadrant_counts: {
      increase_media_investments: number
      maintain_high_salience: number
      maintain_selective: number
      scale_back: number
    }
  }
  signal_snapshot?: AIInsightsSignalSnapshot
  portfolio_metrics?: AIInsightsPortfolioMetrics
  market_cards: AIInsightsMarketCard[]
  ai_brief: string
  ai_summary_json?: AIInsightsSummaryJson | null
  ai_structured?: AIInsightsStructured | null
  notes: string[]
}

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8020'
const normalizeBrandKey = (value: string) => value.toLowerCase().replace(/[^a-z0-9]/g, '')
const SCENARIO_PROGRESS_STAGES = [
  { key: 'queued', label: 'Queued', hint: 'Preparing run context and brand-market payload.', start: 0, end: 10 },
  { key: 'intent', label: 'AI Intent', hint: 'Translating business intent into strategy controls.', start: 10, end: 32 },
  { key: 'sampling', label: 'Sampling', hint: 'Generating diverse feasible scenarios with constraints.', start: 32, end: 76 },
  { key: 'ranking', label: 'Ranking', hint: 'Scoring and ranking by volume and revenue outcomes.', start: 76, end: 101 },
] as const

function getShareGreenColor(sharePct: number) {
  const clamped = Math.max(0, Math.min(100, Number(sharePct) || 0))
  const t = clamped / 100
  const hue = 155 - t * 30
  const saturation = 40 + t * 34
  const lightness = 84 - t * 46
  return `hsl(${hue.toFixed(1)}, ${saturation.toFixed(1)}%, ${lightness.toFixed(1)}%)`
}

function App() {
  const [loadingConfig, setLoadingConfig] = useState(true)
  const [config, setConfig] = useState<AutoConfigResponse | null>(null)

  const [selectedBrand, setSelectedBrand] = useState('')
  const [selectedMarkets, setSelectedMarkets] = useState<string[]>([])
  const [marketSearch, setMarketSearch] = useState('')
  const [marketDropdownOpen, setMarketDropdownOpen] = useState(false)
  const [budgetType, setBudgetType] = useState<'percentage' | 'absolute'>('percentage')
  const [budgetValue, setBudgetValue] = useState<number>(5)
  const [constraintsOpen, setConstraintsOpen] = useState(false)
  const [constraintMarket, setConstraintMarket] = useState<string>('')

  const [isSubmitting, setIsSubmitting] = useState(false)
  const [errorMessage, setErrorMessage] = useState('')
  const [result, setResult] = useState<OptimizeAutoResponse | null>(null)
  const [brandAllocation, setBrandAllocation] = useState<BrandAllocationResponse | null>(null)
  const [brandAllocationLoading, setBrandAllocationLoading] = useState(false)
  const [step1Error, setStep1Error] = useState('')
  const [step1BaselineBudget, setStep1BaselineBudget] = useState<number | null>(null)
  const [step1BaselineLoading, setStep1BaselineLoading] = useState(false)
  const [step1EditMode, setStep1EditMode] = useState(false)
  const [step1EditError, setStep1EditError] = useState('')
  const [step1AllocationDraft, setStep1AllocationDraft] = useState<Record<string, string>>({})
  const [constraintsPreview, setConstraintsPreview] = useState<OptimizeAutoResponse | null>(null)
  const [constraintsLoading, setConstraintsLoading] = useState(false)
  const [marketOverrides, setMarketOverrides] = useState<Record<string, MarketOverride>>({})
  const [activeMainTab, setActiveMainTab] = useState<'s_curves' | 'budget_allocation'>('s_curves')
  const [step2Enabled, setStep2Enabled] = useState(false)
  const [step2SetupCollapsed, setStep2SetupCollapsed] = useState(false)
  const [step1Collapsed, setStep1Collapsed] = useState(false)
  const [scenarioIntent, setScenarioIntent] = useState('')
  const [scenarioJobId, setScenarioJobId] = useState('')
  const [scenarioStatus, setScenarioStatus] = useState<'idle' | 'queued' | 'running' | 'completed' | 'failed' | 'expired'>('idle')
  const [scenarioProgress, setScenarioProgress] = useState(0)
  const [scenarioMessage, setScenarioMessage] = useState('')
  const [scenarioStartedAt, setScenarioStartedAt] = useState<number | null>(null)
  const [scenarioElapsedMs, setScenarioElapsedMs] = useState(0)
  const [scenarioError, setScenarioError] = useState('')
  const [scenarioResults, setScenarioResults] = useState<ScenarioResultsResponse | null>(null)
  const [selectedScenarioId, setSelectedScenarioId] = useState('')
  const [scenarioPage, setScenarioPage] = useState(1)
  const scenarioPageSize = 5
  const [scenarioSortKey, setScenarioSortKey] = useState('revenue_uplift_pct')
  const [scenarioSortDir, setScenarioSortDir] = useState<'asc' | 'desc'>('desc')
  const [scenarioMinRevenuePct, setScenarioMinRevenuePct] = useState('')
  const [scenarioMaxBudgetUtilizedPctFilter, setScenarioMaxBudgetUtilizedPctFilter] = useState('')
  const [scenarioFlowSortKey, setScenarioFlowSortKey] = useState<'share' | 'spend'>('share')
  const [scenarioMarketModal, setScenarioMarketModal] = useState<{ row: ScenarioMarketFlowRow; tone: 'increase' | 'decrease' } | null>(null)
  const [sCurvesData, setSCurvesData] = useState<SCurvesResponse | null>(null)
  const [sCurvesLoading, setSCurvesLoading] = useState(false)
  const [sCurvesError, setSCurvesError] = useState('')
  const [contributionData, setContributionData] = useState<ContributionResponse | null>(null)
  const [contributionLoading, setContributionLoading] = useState(false)
  const [contributionError, setContributionError] = useState('')
  const [yoyData, setYoyData] = useState<YoyGrowthResponse | null>(null)
  const [yoyLoading, setYoyLoading] = useState(false)
  const [yoyError, setYoyError] = useState('')
  const [activeInsightsSection, setActiveInsightsSection] = useState<'curves' | 'contribution' | 'yoy'>('curves')
  const [sCurveStateIndex, setSCurveStateIndex] = useState(0)
  const [aiModeOpen, setAiModeOpen] = useState(false)
  const [aiModeBrand, setAiModeBrand] = useState('')
  const [aiModeLoading, setAiModeLoading] = useState(false)
  const [aiModeError, setAiModeError] = useState('')
  const [aiModeData, setAiModeData] = useState<AIInsightsSummaryResponse | null>(null)
  const latestInsightsSelectionRef = useRef<{ brand: string; market: string }>({ brand: '', market: '' })
  const marketDropdownRef = useRef<HTMLDivElement | null>(null)
  const sCurveRequestSeqRef = useRef(0)
  const contributionRequestSeqRef = useRef(0)
  const yoyRequestSeqRef = useRef(0)

  const step2BrandOptions = useMemo(() => {
    const step1Brands = brandAllocation?.allocation_rows.map((row) => row.brand).filter((brand) => Boolean(brand)) ?? []
    return step1Brands.length > 0 ? step1Brands : (config?.brands ?? [])
  }, [brandAllocation, config])
  const brandLookup = useMemo(() => {
    const lookup: Record<string, string> = {}
    if (!config) return lookup
    for (const brand of Object.keys(config.markets_by_brand)) {
      lookup[normalizeBrandKey(brand)] = brand
    }
    return lookup
  }, [config])
  const resolvedBrandKey = useMemo(() => {
    if (!selectedBrand || !config) return ''
    if (config.markets_by_brand[selectedBrand]) return selectedBrand
    return brandLookup[normalizeBrandKey(selectedBrand)] ?? ''
  }, [selectedBrand, config, brandLookup])
  const availableMarkets = useMemo(
    () => (resolvedBrandKey && config ? config.markets_by_brand[resolvedBrandKey] ?? [] : []),
    [config, resolvedBrandKey],
  )

  const canSubmit = useMemo(
    () => Boolean(selectedBrand && selectedMarkets.length > 0 && !loadingConfig),
    [selectedBrand, selectedMarkets, loadingConfig],
  )
  const filteredMarkets = useMemo(() => {
    const term = marketSearch.trim().toLowerCase()
    if (!term) {
      return availableMarkets
    }
    return availableMarkets.filter((market) => market.toLowerCase().includes(term))
  }, [availableMarkets, marketSearch])
  const selectedMarketsKey = useMemo(() => [...selectedMarkets].sort().join('|'), [selectedMarkets])
  const overridesKey = useMemo(() => JSON.stringify(marketOverrides), [marketOverrides])
  const sCurveStates = useMemo(() => availableMarkets, [availableMarkets])
  const aiModeMarkets = useMemo(() => {
    if (!config || !aiModeBrand) return []
    return config.markets_by_brand[aiModeBrand] ?? []
  }, [config, aiModeBrand])
  const activeSCurveState = useMemo(() => {
    if (sCurveStates.length === 0) return ''
    const safeIdx = Math.max(0, Math.min(sCurveStateIndex, sCurveStates.length - 1))
    return sCurveStates[safeIdx]
  }, [sCurveStates, sCurveStateIndex])

  const ABSOLUTE_BUDGET_UNIT_MN = 1_000_000

  function toBackendBudgetValue(type: 'percentage' | 'absolute', value: number) {
    if (type === 'absolute') {
      return value * ABSOLUTE_BUDGET_UNIT_MN
    }
    return value
  }

  function getStep2BudgetInput() {
    if (!brandAllocation || !selectedBrand) {
      return { budget_increase_type: budgetType as 'percentage' | 'absolute', budget_increase_value: budgetValue }
    }
    const row = brandAllocation.allocation_rows.find((item) => item.brand === selectedBrand)
    if (!row) {
      return { budget_increase_type: budgetType as 'percentage' | 'absolute', budget_increase_value: budgetValue }
    }
    return {
      budget_increase_type: 'absolute' as const,
      budget_increase_value: (row.allocated_budget - row.baseline_budget) / ABSOLUTE_BUDGET_UNIT_MN,
    }
  }

  function getStep2ScenarioBudgetBand() {
    if (!brandAllocation || !selectedBrand) return null
    const row = brandAllocation.allocation_rows.find((item) => item.brand === selectedBrand)
    if (!row) return null
    const upper = Number(row.allocated_budget)
    if (!Number.isFinite(upper) || upper <= 0) return null
    return {
      scenario_budget_lower: 0.8 * upper,
      scenario_budget_upper: upper,
    }
  }

  function resolveScenarioBudgetInput(input: { budget_increase_type: 'percentage' | 'absolute'; budget_increase_value: number }) {
    const backendInput = {
      budget_increase_type: input.budget_increase_type,
      budget_increase_value: toBackendBudgetValue(input.budget_increase_type, input.budget_increase_value),
    }
    const baselineBudget = Number(constraintsPreview?.summary.baseline_budget)
    const feasibleMinBudget = Number(constraintsPreview?.summary.feasible_min_budget)
    const feasibleMaxBudget = Number(constraintsPreview?.summary.feasible_max_budget)
    if (
      !Number.isFinite(baselineBudget) ||
      !Number.isFinite(feasibleMinBudget) ||
      !Number.isFinite(feasibleMaxBudget)
    ) {
      return {
        payload: backendInput,
        adjusted: false,
        requestedTargetBudget: null as number | null,
        adjustedTargetBudget: null as number | null,
        feasibleMinBudget: null as number | null,
        feasibleMaxBudget: null as number | null,
      }
    }
    const requestedTargetBudget =
      backendInput.budget_increase_type === 'percentage'
        ? baselineBudget * (1 + backendInput.budget_increase_value / 100)
        : baselineBudget + backendInput.budget_increase_value
    if (!Number.isFinite(requestedTargetBudget)) {
      return {
        payload: backendInput,
        adjusted: false,
        requestedTargetBudget: null as number | null,
        adjustedTargetBudget: null as number | null,
        feasibleMinBudget,
        feasibleMaxBudget,
      }
    }
    const adjustedTargetBudget = Math.min(Math.max(requestedTargetBudget, feasibleMinBudget), feasibleMaxBudget)
    const eps = Math.max(1, 1e-8 * Math.abs(requestedTargetBudget))
    if (Math.abs(adjustedTargetBudget - requestedTargetBudget) <= eps) {
      return {
        payload: backendInput,
        adjusted: false,
        requestedTargetBudget,
        adjustedTargetBudget,
        feasibleMinBudget,
        feasibleMaxBudget,
      }
    }
    return {
      payload: {
        budget_increase_type: 'absolute' as const,
        budget_increase_value: adjustedTargetBudget - baselineBudget,
      },
      adjusted: true,
      requestedTargetBudget,
      adjustedTargetBudget,
      feasibleMinBudget,
      feasibleMaxBudget,
    }
  }

  useEffect(() => {
    async function loadAutoConfig() {
      setLoadingConfig(true)
      setErrorMessage('')

      try {
        const response = await axios.get<AutoConfigResponse>(`${API_BASE_URL}/api/auto-config`)
        const cfg = response.data
        setConfig(cfg)

        const defaultBrand = cfg.default_brand || cfg.brands[0] || ''
        const defaultMarkets = cfg.markets_by_brand[defaultBrand] ?? []

        setSelectedBrand(defaultBrand)
        setSelectedMarkets(defaultMarkets)
      } catch (error) {
        if (axios.isAxiosError(error)) {
          setErrorMessage(error.response?.data?.detail ?? 'Failed to auto-load configuration.')
        } else {
          setErrorMessage('Unexpected error while loading configuration.')
        }
      } finally {
        setLoadingConfig(false)
      }
    }

    void loadAutoConfig()
  }, [])

  useEffect(() => {
    if (!selectedBrand || !config) {
      return
    }

    setMarketSearch('')
    setMarketDropdownOpen(false)
    setMarketOverrides({})
    const marketsForBrand = availableMarkets
    setSelectedMarkets((prev) => {
      const filtered = prev.filter((market) => marketsForBrand.includes(market))
      return filtered.length > 0 ? filtered : marketsForBrand
    })
  }, [selectedBrand, config, availableMarkets])

  useEffect(() => {
    if (step2BrandOptions.length === 0) return
    if (!step2BrandOptions.includes(selectedBrand)) {
      setSelectedBrand(step2BrandOptions[0])
    }
  }, [step2BrandOptions, selectedBrand])

  useEffect(() => {
    setSCurveStateIndex(0)
  }, [selectedBrand])

  useEffect(() => {
    if (sCurveStates.length === 0) {
      setSCurveStateIndex(0)
      return
    }
    if (sCurveStateIndex > sCurveStates.length - 1) {
      setSCurveStateIndex(sCurveStates.length - 1)
    }
  }, [sCurveStates, sCurveStateIndex])

  useEffect(() => {
    latestInsightsSelectionRef.current = { brand: selectedBrand, market: activeSCurveState }
  }, [selectedBrand, activeSCurveState])

  useEffect(() => {
    if (!aiModeOpen) return
    if (step2BrandOptions.length === 0) return
    if (!aiModeBrand || !step2BrandOptions.includes(aiModeBrand)) {
      if (step2BrandOptions.includes(selectedBrand)) {
        setAiModeBrand(selectedBrand)
      } else {
        setAiModeBrand(step2BrandOptions[0])
      }
    }
  }, [aiModeOpen, aiModeBrand, step2BrandOptions, selectedBrand])

  useEffect(() => {
    if (loadingConfig) return
    let cancelled = false
    async function loadStep1Baseline() {
      try {
        setStep1BaselineLoading(true)
        const response = await axios.post<BrandAllocationResponse>(`${API_BASE_URL}/api/brand-allocation`, {
          budget_increase_type: 'percentage',
          budget_increase_value: 0,
        })
        if (!cancelled) {
          setStep1BaselineBudget(response.data.summary.baseline_total_budget ?? null)
        }
      } catch {
        if (!cancelled) {
          setStep1BaselineBudget(null)
        }
      } finally {
        if (!cancelled) {
          setStep1BaselineLoading(false)
        }
      }
    }
    void loadStep1Baseline()
    return () => {
      cancelled = true
    }
  }, [loadingConfig])

  useEffect(() => {
    if (!brandAllocation) {
      setStep1EditMode(false)
      setStep1EditError('')
      setStep1AllocationDraft({})
      return
    }
    const nextDraft: Record<string, string> = {}
    for (const row of brandAllocation.allocation_rows) {
      nextDraft[row.brand] = String(Number((row.allocated_budget / 1_000_000_000).toFixed(4)))
    }
    setStep1AllocationDraft(nextDraft)
    setStep1EditMode(false)
    setStep1EditError('')
  }, [brandAllocation])

  async function handleRunStep1() {
    setStep1Error('')
    setStep1EditError('')
    setErrorMessage('')
    setStep2Enabled(false)
    setStep2SetupCollapsed(false)
    setStep1Collapsed(false)
    setScenarioJobId('')
    setScenarioStatus('idle')
    setScenarioProgress(0)
    setScenarioMessage('')
    setScenarioError('')
    setScenarioResults(null)
    setSelectedScenarioId('')
    setScenarioPage(1)
    setScenarioMinRevenuePct('')
    setScenarioMaxBudgetUtilizedPctFilter('')

    try {
      setBrandAllocationLoading(true)
      const response = await axios.post<BrandAllocationResponse>(`${API_BASE_URL}/api/brand-allocation`, {
        budget_increase_type: budgetType,
        budget_increase_value: toBackendBudgetValue(budgetType, budgetValue),
      })
      setBrandAllocation(response.data)
    } catch (error) {
      setBrandAllocation(null)
      if (axios.isAxiosError(error)) {
        setStep1Error(error.response?.data?.detail ?? 'Failed to run Step 1.')
      } else {
        setStep1Error('Unexpected error while running Step 1.')
      }
    } finally {
      setBrandAllocationLoading(false)
    }
  }

  function handleStep1DraftChange(brand: string, rawValue: string) {
    setStep1EditError('')
    setStep1AllocationDraft((prev) => ({ ...prev, [brand]: rawValue }))
  }

  function resetStep1AllocationDraft() {
    if (!brandAllocation) return
    const nextDraft: Record<string, string> = {}
    for (const row of brandAllocation.allocation_rows) {
      nextDraft[row.brand] = String(Number((row.allocated_budget / 1_000_000_000).toFixed(4)))
    }
    setStep1AllocationDraft(nextDraft)
  }

  function handleEditStep1Allocations() {
    resetStep1AllocationDraft()
    setStep1EditError('')
    setStep1EditMode(true)
  }

  function handleCancelStep1Allocations() {
    resetStep1AllocationDraft()
    setStep1EditError('')
    setStep1EditMode(false)
  }

  useEffect(() => {
    if (!marketDropdownOpen) return
    const onMouseDown = (event: MouseEvent) => {
      const target = event.target as Node | null
      if (!target) return
      if (marketDropdownRef.current && !marketDropdownRef.current.contains(target)) {
        setMarketDropdownOpen(false)
      }
    }
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setMarketDropdownOpen(false)
      }
    }
    document.addEventListener('mousedown', onMouseDown)
    document.addEventListener('keydown', onKeyDown)
    return () => {
      document.removeEventListener('mousedown', onMouseDown)
      document.removeEventListener('keydown', onKeyDown)
    }
  }, [marketDropdownOpen])

  function handleSaveStep1Allocations() {
    if (!brandAllocation) return
    setStep1EditError('')
    const parsedByBrand: Record<string, number> = {}
    for (const row of brandAllocation.allocation_rows) {
      const raw = step1AllocationDraft[row.brand] ?? ''
      const valueBn = Number(raw)
      if (!Number.isFinite(valueBn) || valueBn < 0) {
        setStep1EditError(`Enter a valid allocated budget in Bn for ${row.brand}.`)
        return
      }
      const nextAllocated = valueBn * 1_000_000_000
      const baselineBudget = Number(row.baseline_budget ?? 0)
      const minAllowed = Number(row.min_allowed_budget ?? baselineBudget * 0.75)
      const maxAllowed = Number(row.max_allowed_budget ?? baselineBudget * 1.25)
      if (nextAllocated < minAllowed - 1 || nextAllocated > maxAllowed + 1) {
        setStep1EditError(
          `${row.brand} must stay within ${formatCurrencyBn(minAllowed)} to ${formatCurrencyBn(maxAllowed)}.`,
        )
        return
      }
      parsedByBrand[row.brand] = nextAllocated
    }
    const editedTotal = Object.values(parsedByBrand).reduce((acc, value) => acc + value, 0)
    const baselineTotal = Number(brandAllocation.summary.baseline_total_budget)
    let baselineTotalVolume = 0
    let estimatedTotalNewVolume = 0
    let baselineTotalRevenue = 0
    let estimatedTotalNewRevenue = 0
    const nextRows = brandAllocation.allocation_rows.map((row) => {
      const nextAllocated = parsedByBrand[row.brand]
      const nextShare = editedTotal > 1e-9 ? nextAllocated / editedTotal : 0
      const baselineBudget = Number(row.baseline_budget ?? 0)
      const baselineVolume = Number(row.baseline_volume ?? 0)
      const effectiveElasticity = Number(row.effective_elasticity ?? row.elasticity ?? 0)
      const avgPrice =
        Number(row.avg_price_last_3_points ?? 0) > 0
          ? Number(row.avg_price_last_3_points)
          : baselineVolume > 1e-9
            ? Number(row.baseline_revenue ?? 0) / baselineVolume
            : 0
      const spendChangeRatio = baselineBudget > 1e-9 ? (nextAllocated - baselineBudget) / baselineBudget : 0
      const volumeUpliftAbs = Math.max(-baselineVolume, baselineVolume * effectiveElasticity * spendChangeRatio)
      const estimatedNewVolume = baselineVolume + volumeUpliftAbs
      const volumeUpliftPct = baselineVolume > 1e-9 ? (volumeUpliftAbs / baselineVolume) * 100 : 0
      const baselineRevenue = baselineVolume * avgPrice
      const estimatedNewRevenue = estimatedNewVolume * avgPrice
      const revenueUpliftAbs = estimatedNewRevenue - baselineRevenue
      const revenueUpliftPct = baselineRevenue > 1e-9 ? (revenueUpliftAbs / baselineRevenue) * 100 : 0

      baselineTotalVolume += baselineVolume
      estimatedTotalNewVolume += estimatedNewVolume
      baselineTotalRevenue += baselineRevenue
      estimatedTotalNewRevenue += estimatedNewRevenue

      return {
        ...row,
        allocated_budget: nextAllocated,
        share: nextShare,
        uplift_amount: nextAllocated - baselineBudget,
        estimated_new_volume: estimatedNewVolume,
        estimated_volume_uplift_abs: volumeUpliftAbs,
        estimated_volume_uplift_pct: volumeUpliftPct,
        baseline_revenue: baselineRevenue,
        estimated_new_revenue: estimatedNewRevenue,
        estimated_revenue_uplift_abs: revenueUpliftAbs,
        estimated_revenue_uplift_pct: revenueUpliftPct,
      }
    })
    const estimatedTotalVolumeUpliftAbs = estimatedTotalNewVolume - baselineTotalVolume
    const estimatedTotalVolumeUpliftPct =
      baselineTotalVolume > 1e-9 ? (estimatedTotalVolumeUpliftAbs / baselineTotalVolume) * 100 : 0
    const estimatedTotalRevenueUpliftAbs = estimatedTotalNewRevenue - baselineTotalRevenue
    const estimatedTotalRevenueUpliftPct =
      baselineTotalRevenue > 1e-9 ? (estimatedTotalRevenueUpliftAbs / baselineTotalRevenue) * 100 : 0
    setBrandAllocation({
      ...brandAllocation,
      summary: {
        ...brandAllocation.summary,
        requested_target_total_budget: editedTotal,
        target_total_budget: editedTotal,
        incremental_budget: editedTotal - baselineTotal,
        baseline_total_volume: baselineTotalVolume,
        estimated_total_new_volume: estimatedTotalNewVolume,
        estimated_total_volume_uplift_abs: estimatedTotalVolumeUpliftAbs,
        estimated_total_volume_uplift_pct: estimatedTotalVolumeUpliftPct,
        baseline_total_revenue: baselineTotalRevenue,
        estimated_total_new_revenue: estimatedTotalNewRevenue,
        estimated_total_revenue_uplift_abs: estimatedTotalRevenueUpliftAbs,
        estimated_total_revenue_uplift_pct: estimatedTotalRevenueUpliftPct,
      },
      allocation_rows: nextRows,
    })
    setStep1EditMode(false)
  }

  useEffect(() => {
    setBrandAllocation(null)
    setStep1Error('')
    setStep2Enabled(false)
    setStep2SetupCollapsed(false)
    setStep1Collapsed(false)
    setResult(null)
    setScenarioJobId('')
    setScenarioStatus('idle')
    setScenarioProgress(0)
    setScenarioMessage('')
    setScenarioError('')
    setScenarioResults(null)
    setSelectedScenarioId('')
    setScenarioPage(1)
    setScenarioMinRevenuePct('')
    setScenarioMaxBudgetUtilizedPctFilter('')
  }, [budgetType, budgetValue])

  useEffect(() => {
    setScenarioJobId('')
    setScenarioStatus('idle')
    setScenarioProgress(0)
    setScenarioMessage('')
    setScenarioError('')
    setScenarioResults(null)
    setSelectedScenarioId('')
    setScenarioPage(1)
    setScenarioMinRevenuePct('')
    setScenarioMaxBudgetUtilizedPctFilter('')
    setStep2SetupCollapsed(false)
  }, [selectedBrand, selectedMarketsKey, overridesKey])

  useEffect(() => {
    if (loadingConfig || !selectedBrand || selectedMarkets.length === 0) {
      setConstraintsPreview(null)
      return
    }

    let cancelled = false
    async function loadConstraintsPreview() {
      try {
        setConstraintsLoading(true)
        const step2BudgetInput = getStep2BudgetInput()
        const response = await axios.post<OptimizeAutoResponse>(`${API_BASE_URL}/api/constraints-auto`, {
          selected_brand: selectedBrand,
          selected_markets: selectedMarkets,
          budget_increase_type: step2BudgetInput.budget_increase_type,
          budget_increase_value: toBackendBudgetValue(
            step2BudgetInput.budget_increase_type,
            step2BudgetInput.budget_increase_value,
          ),
          market_overrides: marketOverrides,
        })
        if (!cancelled) {
          setConstraintsPreview(response.data)
        }
      } catch {
        if (!cancelled) {
          setConstraintsPreview(null)
        }
      } finally {
        if (!cancelled) {
          setConstraintsLoading(false)
        }
      }
    }

    void loadConstraintsPreview()
    return () => {
      cancelled = true
    }
  }, [loadingConfig, selectedBrand, selectedMarketsKey, budgetType, budgetValue, brandAllocation, overridesKey])

  useEffect(() => {
    if (activeMainTab !== 's_curves') {
      return
    }
    if (loadingConfig || !selectedBrand || !activeSCurveState) {
      setSCurvesData(null)
      setContributionData(null)
      setYoyData(null)
      return
    }
    void loadSCurves()
    void loadContributionInsights()
    void loadYoyGrowth()
  }, [activeMainTab, loadingConfig, selectedBrand, activeSCurveState])

  function toggleMarket(market: string) {
    setSelectedMarkets((prev) =>
      prev.includes(market) ? prev.filter((item) => item !== market) : [...prev, market],
    )
  }

  function updateMarketOverride(market: string, key: keyof MarketOverride, rawValue: string) {
    setMarketOverrides((prev) => {
      const current = prev[market] ?? {}
      const trimmed = rawValue.trim()
      const nextValue = trimmed === '' ? undefined : Number(trimmed)
      const nextMarket: MarketOverride = {
        ...current,
        [key]: nextValue != null && Number.isFinite(nextValue) ? nextValue : undefined,
      }
      const hasAny = Object.values(nextMarket).some((value) => value != null && Number.isFinite(value))
      if (!hasAny) {
        const clone = { ...prev }
        delete clone[market]
        return clone
      }
      return { ...prev, [market]: nextMarket }
    })
  }

  async function loadSCurves() {
    if (!selectedBrand || !activeSCurveState) {
      setSCurvesData(null)
      return
    }
    const requestId = ++sCurveRequestSeqRef.current
    const brandAtRequest = selectedBrand
    const marketAtRequest = activeSCurveState
    try {
      setSCurvesLoading(true)
      setSCurvesError('')
      const response = await axios.post<SCurvesResponse>(`${API_BASE_URL}/api/s-curves-auto`, {
        selected_brand: brandAtRequest,
        selected_markets: [marketAtRequest],
        points: 41,
        min_scale: 0.2,
        max_scale: 2.5,
      })
      if (requestId !== sCurveRequestSeqRef.current) return
      const current = latestInsightsSelectionRef.current
      if (current.brand !== brandAtRequest || current.market !== marketAtRequest) return
      setSCurvesData(response.data)
    } catch (error) {
      if (requestId !== sCurveRequestSeqRef.current) return
      setSCurvesData(null)
      if (axios.isAxiosError(error)) {
        setSCurvesError(error.response?.data?.detail ?? 'Failed to load S-curves.')
      } else {
        setSCurvesError('Failed to load S-curves.')
      }
    } finally {
      if (requestId === sCurveRequestSeqRef.current) {
        setSCurvesLoading(false)
      }
    }
  }

  async function loadContributionInsights() {
    if (!selectedBrand || !activeSCurveState) {
      setContributionData(null)
      return
    }
    const requestId = ++contributionRequestSeqRef.current
    const brandAtRequest = selectedBrand
    const marketAtRequest = activeSCurveState
    try {
      setContributionLoading(true)
      setContributionError('')
      const response = await axios.post<ContributionResponse>(`${API_BASE_URL}/api/contributions-auto`, {
        selected_brand: brandAtRequest,
        selected_market: marketAtRequest,
        top_n: 8,
      })
      if (requestId !== contributionRequestSeqRef.current) return
      const current = latestInsightsSelectionRef.current
      if (current.brand !== brandAtRequest || current.market !== marketAtRequest) return
      setContributionData(response.data)
    } catch (error) {
      if (requestId !== contributionRequestSeqRef.current) return
      setContributionData(null)
      if (axios.isAxiosError(error)) {
        setContributionError(error.response?.data?.detail ?? 'Failed to load contribution insights.')
      } else {
        setContributionError('Failed to load contribution insights.')
      }
    } finally {
      if (requestId === contributionRequestSeqRef.current) {
        setContributionLoading(false)
      }
    }
  }

  async function loadYoyGrowth() {
    if (!selectedBrand || !activeSCurveState) {
      setYoyData(null)
      return
    }
    const requestId = ++yoyRequestSeqRef.current
    const brandAtRequest = selectedBrand
    const marketAtRequest = activeSCurveState
    try {
      setYoyLoading(true)
      setYoyError('')
      const response = await axios.post<YoyGrowthResponse>(`${API_BASE_URL}/api/yoy-growth-auto`, {
        selected_brand: brandAtRequest,
        selected_market: marketAtRequest,
      })
      if (requestId !== yoyRequestSeqRef.current) return
      const current = latestInsightsSelectionRef.current
      if (current.brand !== brandAtRequest || current.market !== marketAtRequest) return
      setYoyData(response.data)
    } catch (error) {
      if (requestId !== yoyRequestSeqRef.current) return
      setYoyData(null)
      if (axios.isAxiosError(error)) {
        setYoyError(error.response?.data?.detail ?? 'Failed to load YoY growth insights.')
      } else {
        setYoyError('Failed to load YoY growth insights.')
      }
    } finally {
      if (requestId === yoyRequestSeqRef.current) {
        setYoyLoading(false)
      }
    }
  }

  function openAiModeModal() {
    const preferredBrand = step2BrandOptions.includes(selectedBrand) ? selectedBrand : step2BrandOptions[0] ?? ''
    setAiModeBrand(preferredBrand)
    setAiModeError('')
    setAiModeData(null)
    setAiModeOpen(true)
  }

  function closeAiModeModal() {
    setAiModeOpen(false)
    setAiModeLoading(false)
  }

  async function handleGenerateAiInsights() {
    if (!config) {
      setAiModeError('Configuration is not loaded yet.')
      return
    }
    if (!aiModeBrand) {
      setAiModeError('Please select a brand.')
      return
    }
    const payloadMarkets = config.markets_by_brand[aiModeBrand] ?? []
    if (payloadMarkets.length === 0) {
      setAiModeError('No markets available for selected brand.')
      return
    }
    const autoContext = {
      insights_brand: aiModeBrand,
      insights_market: activeSCurveState,
      s_curve: sCurvesData
        ? {
            tv_points: sCurvesData.curves.tv.length,
            digital_points: sCurvesData.curves.digital.length,
            tv_first_uplift_pct: sCurvesData.curves.tv[0]?.volume_uplift_pct ?? 0,
            tv_last_uplift_pct: sCurvesData.curves.tv[sCurvesData.curves.tv.length - 1]?.volume_uplift_pct ?? 0,
            dg_first_uplift_pct: sCurvesData.curves.digital[0]?.volume_uplift_pct ?? 0,
            dg_last_uplift_pct: sCurvesData.curves.digital[sCurvesData.curves.digital.length - 1]?.volume_uplift_pct ?? 0,
          }
        : null,
      contribution_top: (contributionData?.items ?? []).slice(0, 5).map((item) => ({
        variable: item.label,
        abs: item.absolute_contribution,
        share_pct: item.share_pct,
      })),
      yoy: yoyData
        ? {
            latest_fiscal_year: yoyData.summary.latest_fiscal_year,
            latest_yoy_growth_pct: yoyData.summary.latest_yoy_growth_pct,
            latest_volume_mn: yoyData.summary.latest_volume_mn,
          }
        : null,
    }
    const filteredOverrides = Object.fromEntries(
      Object.entries(marketOverrides).filter(([market]) => payloadMarkets.includes(market)),
    )
    try {
      setAiModeLoading(true)
      setAiModeError('')
      const step2BudgetInput = getStep2BudgetInput()
      const requestBody = {
        selected_brand: aiModeBrand,
        selected_markets: payloadMarkets,
        budget_increase_type: step2BudgetInput.budget_increase_type,
        budget_increase_value: toBackendBudgetValue(
          step2BudgetInput.budget_increase_type,
          step2BudgetInput.budget_increase_value,
        ),
        market_overrides: filteredOverrides,
        focus_prompt: JSON.stringify(autoContext),
      }
      const endpoints = ['/api/trinity-report', '/api/insights-ai-summary', '/api/insights-ai']
      let response: { data: AIInsightsSummaryResponse } | null = null
      let lastError: unknown = null
      for (const endpoint of endpoints) {
        try {
          response = await axios.post<AIInsightsSummaryResponse>(`${API_BASE_URL}${endpoint}`, requestBody)
          break
        } catch (error) {
          lastError = error
          if (!axios.isAxiosError(error) || error.response?.status !== 404) {
            throw error
          }
        }
      }
      if (!response) {
        throw lastError ?? new Error('No Trinity endpoint available.')
      }
      setAiModeData(response.data)
    } catch (error) {
      setAiModeData(null)
      if (axios.isAxiosError(error)) {
        setAiModeError(error.response?.data?.detail ?? 'Failed to generate AI insights.')
      } else {
        setAiModeError('Failed to generate AI insights.')
      }
    } finally {
      setAiModeLoading(false)
    }
  }

  async function fetchScenarioResults(jobId: string, page = scenarioPage) {
    const params: Record<string, string | number> = {
      page,
      page_size: scenarioPageSize,
      sort_key: scenarioSortKey,
      sort_dir: scenarioSortDir,
    }
    if (scenarioMinRevenuePct.trim() !== '') params.min_revenue_uplift_pct = Number(scenarioMinRevenuePct)
    if (scenarioMaxBudgetUtilizedPctFilter.trim() !== '') params.max_budget_utilized_pct = Number(scenarioMaxBudgetUtilizedPctFilter)
    const response = await axios.get<ScenarioResultsResponse>(`${API_BASE_URL}/api/scenarios/jobs/${jobId}/results`, {
      params,
      validateStatus: (status) => [200, 202, 409, 410].includes(status),
    })
    if (response.status === 200) {
      setScenarioResults(response.data)
      setScenarioPage(response.data.pagination.page)
      setScenarioError('')
      return
    }
    if (response.status === 202) {
      setScenarioStatus('running')
      setScenarioProgress((response.data as { progress?: number }).progress ?? scenarioProgress)
      return
    }
    const payload = response.data as { error_reason?: string }
    setScenarioError(payload.error_reason ?? 'Failed to load scenario results.')
  }

  async function handleGenerateScenarios(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setErrorMessage('')
    setScenarioError('')
    setScenarioResults(null)
    setSelectedScenarioId('')

    if (!selectedBrand || selectedMarkets.length === 0) {
      setScenarioError('Please select a brand and at least one market.')
      return
    }

    try {
      setIsSubmitting(true)
      setScenarioStartedAt(Date.now())
      setScenarioElapsedMs(0)
      const step2BudgetInput = getStep2BudgetInput()
      const resolvedBudget = resolveScenarioBudgetInput(step2BudgetInput)
      const scenarioBudgetBand = getStep2ScenarioBudgetBand()
      const response = await axios.post<ScenarioJobCreateResponse>(`${API_BASE_URL}/api/scenarios/jobs`, {
        selected_brand: selectedBrand,
        selected_markets: selectedMarkets,
        budget_increase_type: resolvedBudget.payload.budget_increase_type,
        budget_increase_value: resolvedBudget.payload.budget_increase_value,
        scenario_budget_lower: scenarioBudgetBand?.scenario_budget_lower,
        scenario_budget_upper: scenarioBudgetBand?.scenario_budget_upper,
        market_overrides: marketOverrides,
        intent_prompt: scenarioIntent,
      })
      setScenarioJobId(response.data.job_id)
      setScenarioStatus(response.data.status)
      setScenarioProgress(response.data.progress ?? 0)
      setScenarioMessage(response.data.message ?? 'Scenario generation queued.')
      setScenarioPage(1)
      setStep2SetupCollapsed(true)
    } catch (error) {
      setScenarioStartedAt(null)
      setScenarioElapsedMs(0)
      setStep2SetupCollapsed(false)
      if (axios.isAxiosError(error)) {
        setScenarioError(error.response?.data?.detail ?? 'Failed to start scenario generation.')
      } else {
        setScenarioError('Unexpected error while starting scenario generation.')
      }
    } finally {
      setIsSubmitting(false)
    }
  }

  useEffect(() => {
    if (!scenarioJobId) return
    if (!(scenarioStatus === 'queued' || scenarioStatus === 'running')) return

    const timer = setInterval(() => {
      void (async () => {
        try {
          const response = await axios.get<ScenarioJobStatusResponse>(`${API_BASE_URL}/api/scenarios/jobs/${scenarioJobId}`)
          const nextStatus = response.data.status
          setScenarioStatus(nextStatus)
          setScenarioProgress(response.data.progress ?? 0)
          setScenarioMessage(response.data.message ?? '')
          if (nextStatus === 'completed') {
            await fetchScenarioResults(scenarioJobId, 1)
          } else if (nextStatus === 'failed' || nextStatus === 'expired') {
            setScenarioStartedAt(null)
            setScenarioError(response.data.error_reason ?? 'Scenario generation failed.')
          }
        } catch (error) {
          setScenarioStartedAt(null)
          if (axios.isAxiosError(error) && error.response?.status === 404) {
            setScenarioStatus('idle')
            setScenarioJobId('')
            setScenarioProgress(0)
            setScenarioMessage('')
            setScenarioError('Scenario job not found (backend was likely restarted). Please generate scenarios again.')
            return
          }
          setScenarioError('Unable to fetch scenario job status.')
        }
      })()
    }, 2000)

    return () => clearInterval(timer)
  }, [scenarioJobId, scenarioStatus])

  useEffect(() => {
    if (!(scenarioStatus === 'queued' || scenarioStatus === 'running') || !scenarioStartedAt) return
    const timer = setInterval(() => {
      setScenarioElapsedMs(Date.now() - scenarioStartedAt)
    }, 1000)
    return () => clearInterval(timer)
  }, [scenarioStatus, scenarioStartedAt])

  useEffect(() => {
    if (!scenarioJobId || scenarioStatus !== 'completed') return
    void fetchScenarioResults(scenarioJobId, scenarioPage)
  }, [scenarioPage, scenarioPageSize, scenarioSortKey, scenarioSortDir, scenarioMinRevenuePct, scenarioMaxBudgetUtilizedPctFilter])

  const moneyFormatter = useMemo(
    () =>
      new Intl.NumberFormat('en-IN', {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
      }),
    [],
  )
  const numberFormatter = useMemo(
    () =>
      new Intl.NumberFormat('en-IN', {
        maximumFractionDigits: 2,
      }),
    [],
  )
  const formatCurrencyBn = (value?: number | null) =>
    value == null || Number.isNaN(value) ? '-' : `INR ${moneyFormatter.format(value / 1_000_000_000)} Bn`
  const formatCurrencyMn = (value?: number | null) =>
    value == null || Number.isNaN(value) ? '-' : `INR ${moneyFormatter.format(value / 1_000_000)} Mn`
  const formatSignedCurrencyBn = (value?: number | null) => {
    if (value == null || Number.isNaN(value)) return '-'
    const base = moneyFormatter.format(Math.abs(value) / 1_000_000_000)
    if (value > 0) return `INR +${base} Bn`
    if (value < 0) return `INR -${base} Bn`
    return `INR ${base} Bn`
  }
  const formatSignedCurrencyMn = (value?: number | null) => {
    if (value == null || Number.isNaN(value)) return '-'
    const base = moneyFormatter.format(Math.abs(value))
    if (value > 0) return `INR +${base} Mn`
    if (value < 0) return `INR -${base} Mn`
    return `INR ${base} Mn`
  }
  const formatRawNumber = (value?: number | null) =>
    value == null || Number.isNaN(value) ? '-' : numberFormatter.format(value)
  const formatPct = (value?: number | null, digits = 2) =>
    value == null || Number.isNaN(value) ? '-' : `${value.toFixed(digits)}%`
  const formatSignedPct = (value?: number | null, digits = 2) =>
    value == null || Number.isNaN(value) ? '-' : `${value >= 0 ? '+' : ''}${value.toFixed(digits)}%`
  const formatSignedNumber = (value?: number | null, digits = 2) =>
    value == null || Number.isNaN(value) ? '-' : `${value >= 0 ? '+' : ''}${value.toFixed(digits)}`
  const constraintRows = useMemo(() => {
    const rows = result?.allocation_rows ?? constraintsPreview?.allocation_rows ?? []
    return [...rows].sort((a, b) => a.market.localeCompare(b.market))
  }, [result, constraintsPreview])

  useEffect(() => {
    if (constraintRows.length === 0) {
      setConstraintMarket('')
      return
    }
    if (!constraintRows.some((row) => row.market === constraintMarket)) {
      setConstraintMarket(constraintRows[0].market)
    }
  }, [constraintRows, constraintMarket])

  const selectedConstraintRow = useMemo(() => {
    if (constraintRows.length === 0) return null
    return constraintRows.find((row) => row.market === constraintMarket) ?? constraintRows[0] ?? null
  }, [constraintRows, constraintMarket])
  const activeConstraintSummary = result?.summary ?? constraintsPreview?.summary ?? null
  const selectedBrandAllocation = useMemo(() => {
    if (!brandAllocation || !selectedBrand) return null
    return brandAllocation.allocation_rows.find((row) => row.brand === selectedBrand) ?? null
  }, [brandAllocation, selectedBrand])
  const showIncrementalBudget = useMemo(() => {
    if (!brandAllocation) return false
    return Math.abs(brandAllocation.summary.incremental_budget) > 1e-6
  }, [brandAllocation])
  const step1SplitRows = useMemo(() => {
    if (!brandAllocation) return []
    const baselineTotal = Number(brandAllocation.summary.baseline_total_budget ?? 0)
    const optimizedTotal = Number(brandAllocation.summary.target_total_budget ?? 0)
    return brandAllocation.allocation_rows.map((row) => {
      const baselineBudget = Number(row.baseline_budget ?? 0)
      const allocatedBudget = Number(row.allocated_budget ?? 0)
      const baselineShare = baselineTotal > 1e-9 ? (baselineBudget / baselineTotal) * 100 : 0
      const optimizedShare = optimizedTotal > 1e-9 ? (allocatedBudget / optimizedTotal) * 100 : 0
      return {
        brand: row.brand,
        baselineBudget,
        allocatedBudget,
        baselineShare,
        optimizedShare,
      }
    })
  }, [brandAllocation])
  const step1EditedTotalBudget = useMemo(() => {
    if (!brandAllocation) return null
    if (!step1EditMode) return Number(brandAllocation.summary.target_total_budget)
    return brandAllocation.allocation_rows.reduce((acc, row) => {
      const draftBn = Number(step1AllocationDraft[row.brand])
      if (Number.isFinite(draftBn) && draftBn >= 0) return acc + draftBn * 1_000_000_000
      return acc + Number(row.allocated_budget ?? 0)
    }, 0)
  }, [brandAllocation, step1EditMode, step1AllocationDraft])
  const selectedScenario = useMemo(() => {
    if (!scenarioResults || !selectedScenarioId) return null
    return scenarioResults.items.find((item) => item.scenario_id === selectedScenarioId) ?? null
  }, [scenarioResults, selectedScenarioId])
  const selectedScenarioOriginalSpendTotal = useMemo(() => {
    if (!selectedScenario) return 0
    return selectedScenario.markets.reduce((acc, row) => acc + Number(row.old_total_spend ?? 0), 0)
  }, [selectedScenario])
  const selectedScenarioBudgetFlow = useMemo(() => {
    if (!selectedScenario) {
      return {
        increased: [] as ScenarioMarketFlowRow[],
        decreased: [] as ScenarioMarketFlowRow[],
        maxShareDeltaPct: 0.1,
        maxSpendDeltaMn: 1,
      }
    }
    const totalNewSpend = Number(selectedScenario.total_new_spend ?? 0)
    const rows = selectedScenario.markets.map((row) => {
      const oldSpend = Number(row.old_total_spend ?? 0)
      const oldBudgetSharePct =
        selectedScenarioOriginalSpendTotal > 1e-12
          ? (oldSpend / selectedScenarioOriginalSpendTotal) * 100
          : 0
      const newBudgetSharePct = Number(row.new_budget_share ?? 0) * 100
      const budgetShareChangePct = newBudgetSharePct - oldBudgetSharePct
      const newSpend =
        row.new_total_spend != null && Number.isFinite(Number(row.new_total_spend))
          ? Number(row.new_total_spend)
          : totalNewSpend * Number(row.new_budget_share ?? 0)
      const spendDeltaMn = (newSpend - oldSpend) / 1_000_000
      const oldTvPct = Number(row.fy25_tv_share ?? row.tv_split ?? 0) * 100
      const newTvPct = Number(row.tv_split ?? 0) * 100
      const oldDigitalPct = Number(row.fy25_digital_share ?? row.digital_split ?? 0) * 100
      const newDigitalPct = Number(row.digital_split ?? 0) * 100
      return {
        market: row.market,
        old_budget_share_pct: oldBudgetSharePct,
        new_budget_share_pct: newBudgetSharePct,
        budget_share_change_pct: budgetShareChangePct,
        spend_delta_mn: spendDeltaMn,
        old_tv_split_pct: oldTvPct,
        new_tv_split_pct: newTvPct,
        tv_split_change_pct: newTvPct - oldTvPct,
        old_digital_split_pct: oldDigitalPct,
        new_digital_split_pct: newDigitalPct,
        digital_split_change_pct: newDigitalPct - oldDigitalPct,
      }
    })
    const sorter: (a: ScenarioMarketFlowRow, b: ScenarioMarketFlowRow) => number =
      scenarioFlowSortKey === 'spend'
        ? (a, b) => Math.abs(b.spend_delta_mn) - Math.abs(a.spend_delta_mn)
        : (a, b) =>
            Math.abs(b.budget_share_change_pct) - Math.abs(a.budget_share_change_pct)
    const increased = rows.filter((row) => row.budget_share_change_pct > 0.001).sort(sorter)
    const decreased = rows.filter((row) => row.budget_share_change_pct < -0.001).sort(sorter)
    const maxShareDeltaPct = Math.max(0.1, ...rows.map((row) => Math.abs(row.budget_share_change_pct)))
    const maxSpendDeltaMn = Math.max(1, ...rows.map((row) => Math.abs(row.spend_delta_mn)))
    return { increased, decreased, maxShareDeltaPct, maxSpendDeltaMn }
  }, [selectedScenario, selectedScenarioOriginalSpendTotal, scenarioFlowSortKey])
  const scenarioChartWidth = 1200
  const scenarioPageRange = useMemo(() => {
    if (!scenarioResults || scenarioResults.items.length === 0) {
      return { start: 0, end: 0 }
    }
    const start = (scenarioResults.pagination.page - 1) * scenarioResults.pagination.page_size + 1
    const end = start + scenarioResults.items.length - 1
    return { start, end }
  }, [scenarioResults])
  const scenarioBudgetAxisMax = useMemo(() => {
    const items = scenarioResults?.items ?? []
    if (items.length === 0) return 100
    const targetBudget = Number(scenarioResults?.summary.target_budget ?? 0)
    if (!Number.isFinite(targetBudget) || targetBudget <= 0) return 100
    const maxPct = Math.max(...items.map((item) => (Number(item.total_new_spend ?? 0) / targetBudget) * 100))
    const rounded = Math.ceil(maxPct / 10) * 10
    return Math.max(100, rounded)
  }, [scenarioResults])
  const scenarioMaxBudgetUtilizedPct = useMemo(() => {
    const items = scenarioResults?.items ?? []
    if (items.length === 0) return 0
    const targetBudget = Number(scenarioResults?.summary.target_budget ?? 0)
    if (!Number.isFinite(targetBudget) || targetBudget <= 0) return 0
    return Math.max(...items.map((item) => (Number(item.total_new_spend ?? 0) / targetBudget) * 100))
  }, [scenarioResults])
  const scenarioGenerationActive = scenarioStatus === 'queued' || scenarioStatus === 'running'
  const normalizedScenarioProgress = Math.max(0, Math.min(100, scenarioProgress))
  const activeScenarioStageIndex = useMemo(() => {
    if (scenarioStatus === 'queued') return 0
    const stageIndex = SCENARIO_PROGRESS_STAGES.findIndex(
      (stage) => normalizedScenarioProgress >= stage.start && normalizedScenarioProgress < stage.end,
    )
    return stageIndex >= 0 ? stageIndex : SCENARIO_PROGRESS_STAGES.length - 1
  }, [scenarioStatus, normalizedScenarioProgress])
  const activeScenarioStage = SCENARIO_PROGRESS_STAGES[activeScenarioStageIndex] ?? SCENARIO_PROGRESS_STAGES[0]
  const scenarioElapsedLabel = useMemo(() => {
    if (!scenarioStartedAt) return '0s'
    const totalSeconds = Math.max(0, Math.floor(scenarioElapsedMs / 1000))
    if (totalSeconds < 60) return `${totalSeconds}s`
    const minutes = Math.floor(totalSeconds / 60)
    const seconds = totalSeconds % 60
    return `${minutes}m ${seconds}s`
  }, [scenarioElapsedMs, scenarioStartedAt])
  const scenarioActivityBars = useMemo(
    () => [
      {
        key: 'intent',
        label: 'Intent translation',
        pct: Math.min(100, normalizedScenarioProgress * 2.4),
      },
      {
        key: 'sampling',
        label: 'Scenario sampling',
        pct: Math.max(6, Math.min(100, (normalizedScenarioProgress - 18) * 1.7)),
      },
      {
        key: 'ranking',
        label: 'Constraint checks + ranking',
        pct: Math.max(4, Math.min(100, (normalizedScenarioProgress - 56) * 2.2)),
      },
    ],
    [normalizedScenarioProgress],
  )

  useEffect(() => {
    const items = scenarioResults?.items ?? []
    if (items.length === 0) {
      if (selectedScenarioId) setSelectedScenarioId('')
      return
    }
    if (selectedScenarioId && !items.some((item) => item.scenario_id === selectedScenarioId)) {
      setSelectedScenarioId('')
    }
  }, [scenarioResults, selectedScenarioId])

  useEffect(() => {
    setScenarioMarketModal(null)
  }, [selectedScenarioId])

  function renderConstraintsPanel() {
    if (constraintsLoading && !selectedConstraintRow && !activeConstraintSummary) {
      return (
        <section className="rounded-xl border border-slate-200 bg-white p-4 shadow-panel">
          <p className="text-sm text-slate-500">Loading constraints preview...</p>
        </section>
      )
    }
    if (!selectedConstraintRow || !activeConstraintSummary) return null
    const currentOverride = marketOverrides[selectedConstraintRow.market] ?? {}

    return (
      <section className="rounded-lg border border-slate-200 bg-white">
        <button
          type="button"
          onClick={() => setConstraintsOpen((prev) => !prev)}
          className="flex w-full items-center justify-between px-3 py-2.5 text-left hover:bg-slate-50"
        >
          <div className="flex items-center gap-2">
            <ShieldCheck className="h-4 w-4 text-primary" />
            <div>
              <p className="text-sm font-semibold text-dark-text">Optimization Constraints</p>
              <p className="text-xs text-slate-500">Budget, CPR, and market-level bounds from model files</p>
            </div>
          </div>
          {constraintsOpen ? (
            <ChevronUp className="h-4 w-4 text-slate-500" />
          ) : (
            <ChevronDown className="h-4 w-4 text-slate-500" />
          )}
        </button>

        {constraintsOpen ? (
          <div className="space-y-3 border-t border-slate-200 bg-slate-50 p-3">
            <div className="rounded-lg border border-slate-200 bg-white p-2.5">
              <div className="flex flex-col gap-2.5">
                <div className="w-full lg:w-80">
                  <label htmlFor="constraint-market" className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                    Market
                  </label>
                  <select
                    id="constraint-market"
                    value={constraintMarket}
                    onChange={(event) => setConstraintMarket(event.target.value)}
                    className="mt-1 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-700 focus:border-[#2563EB] focus:outline-none focus:ring-2 focus:ring-blue-200"
                  >
                    {constraintRows.map((row) => (
                      <option key={row.market} value={row.market}>
                        {row.market}
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              <div className="mt-2 grid gap-2.5 lg:grid-cols-2">
                <div className="rounded-lg border border-slate-200 bg-slate-50 p-2.5">
                  <div className="flex items-center gap-2">
                    <SlidersHorizontal className="h-4 w-4 text-primary" />
                    <p className="text-xs font-semibold uppercase tracking-wide text-neutral">CPR</p>
                  </div>
                  <div className="mt-2 grid grid-cols-2 gap-2 text-sm">
                    <div>
                      <label className="text-slate-500">TV CPR</label>
                      <input
                        type="number"
                        min="0"
                        step="0.0001"
                        value={currentOverride.tv_cpr ?? selectedConstraintRow.tv_cpr ?? ''}
                        onChange={(event) => updateMarketOverride(selectedConstraintRow.market, 'tv_cpr', event.target.value)}
                        className="mt-1 w-full rounded-lg border border-slate-300 bg-white px-2 py-1.5 text-sm text-slate-700 focus:border-[#2563EB] focus:outline-none focus:ring-2 focus:ring-blue-200"
                      />
                    </div>
                    <div>
                      <label className="text-slate-500">Digital CPR</label>
                      <input
                        type="number"
                        min="0"
                        step="0.0001"
                        value={currentOverride.digital_cpr ?? selectedConstraintRow.digital_cpr ?? ''}
                        onChange={(event) => updateMarketOverride(selectedConstraintRow.market, 'digital_cpr', event.target.value)}
                        className="mt-1 w-full rounded-lg border border-slate-300 bg-white px-2 py-1.5 text-sm text-slate-700 focus:border-[#2563EB] focus:outline-none focus:ring-2 focus:ring-blue-200"
                      />
                    </div>
                  </div>
                </div>

                <div className="rounded-lg border border-slate-200 bg-slate-50 p-2.5">
                  <p className="text-xs font-semibold uppercase tracking-wide text-neutral">Budget Constraints</p>
                  <div className="mt-2 grid grid-cols-2 gap-2 text-sm">
                    <div>
                      <label className="text-slate-500">Min TV Spend</label>
                      <input
                        type="number"
                        min="0"
                        step="any"
                        value={currentOverride.min_tv_spend ?? selectedConstraintRow.min_tv_spend ?? ''}
                        onChange={(event) => updateMarketOverride(selectedConstraintRow.market, 'min_tv_spend', event.target.value)}
                        className="mt-1 w-full rounded-lg border border-slate-300 bg-white px-2 py-1.5 text-sm text-slate-700 focus:border-[#2563EB] focus:outline-none focus:ring-2 focus:ring-blue-200"
                      />
                    </div>
                    <div>
                      <label className="text-slate-500">Max TV Spend</label>
                      <input
                        type="number"
                        min="0"
                        step="any"
                        value={currentOverride.max_tv_spend ?? selectedConstraintRow.max_tv_spend ?? ''}
                        onChange={(event) => updateMarketOverride(selectedConstraintRow.market, 'max_tv_spend', event.target.value)}
                        className="mt-1 w-full rounded-lg border border-slate-300 bg-white px-2 py-1.5 text-sm text-slate-700 focus:border-[#2563EB] focus:outline-none focus:ring-2 focus:ring-blue-200"
                      />
                    </div>
                    <div>
                      <label className="text-slate-500">Min Digital Spend</label>
                      <input
                        type="number"
                        min="0"
                        step="any"
                        value={currentOverride.min_digital_spend ?? selectedConstraintRow.min_digital_spend ?? ''}
                        onChange={(event) => updateMarketOverride(selectedConstraintRow.market, 'min_digital_spend', event.target.value)}
                        className="mt-1 w-full rounded-lg border border-slate-300 bg-white px-2 py-1.5 text-sm text-slate-700 focus:border-[#2563EB] focus:outline-none focus:ring-2 focus:ring-blue-200"
                      />
                    </div>
                    <div>
                      <label className="text-slate-500">Max Digital Spend</label>
                      <input
                        type="number"
                        min="0"
                        step="any"
                        value={currentOverride.max_digital_spend ?? selectedConstraintRow.max_digital_spend ?? ''}
                        onChange={(event) => updateMarketOverride(selectedConstraintRow.market, 'max_digital_spend', event.target.value)}
                        className="mt-1 w-full rounded-lg border border-slate-300 bg-white px-2 py-1.5 text-sm text-slate-700 focus:border-[#2563EB] focus:outline-none focus:ring-2 focus:ring-blue-200"
                      />
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        ) : null}
      </section>
    )
  }

  function renderStep1Controls(idPrefix: string) {
    return (
      <div className="rounded-xl border border-slate-200 bg-white p-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Step 1 Inputs</p>
            <p className="mt-0.5 text-xs text-slate-500">Per-brand budget change is constrained between -25% and +25%.</p>
          </div>
          <div className="flex items-center gap-2">
            <div className="rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold text-slate-600">AER Portfolio</div>
            <button
              type="button"
              onClick={() => void handleRunStep1()}
              disabled={brandAllocationLoading}
              className="rounded-lg bg-primary px-3 py-1.5 text-xs font-semibold text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:bg-slate-400"
            >
              {brandAllocationLoading ? 'Running...' : brandAllocation ? 'Re-Run Step 1' : 'Run Step 1'}
            </button>
          </div>
        </div>
        <div className="mt-2 grid gap-2 sm:grid-cols-2">
          <div className="rounded-lg border border-slate-200 bg-slate-50 p-2.5">
            <label className="text-xs font-semibold uppercase tracking-wide text-slate-500" htmlFor={`${idPrefix}-budget-type`}>
              Budget Increase Type
            </label>
            <select
              id={`${idPrefix}-budget-type`}
              value={budgetType}
              onChange={(event) => setBudgetType(event.target.value === 'absolute' ? 'absolute' : 'percentage')}
              className="mt-1 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-700 focus:border-[#2563EB] focus:outline-none focus:ring-2 focus:ring-blue-200"
              disabled={loadingConfig}
            >
              <option value="percentage">Percentage (%)</option>
              <option value="absolute">Absolute Amount (INR Mn)</option>
            </select>
          </div>
          <div className="rounded-lg border border-slate-200 bg-slate-50 p-2.5">
            <label className="text-xs font-semibold uppercase tracking-wide text-slate-500" htmlFor={`${idPrefix}-budget-value`}>
              {budgetType === 'percentage' ? 'Budget Increase %' : 'Absolute Increase Value (Mn)'}
            </label>
            <input
              id={`${idPrefix}-budget-value`}
              type="number"
              step={budgetType === 'percentage' ? '0.001' : '1'}
              value={budgetValue}
              onChange={(event) => setBudgetValue(Number(event.target.value))}
              inputMode="decimal"
              className="no-spinner mt-1 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-700 focus:border-[#2563EB] focus:outline-none focus:ring-2 focus:ring-blue-200"
              disabled={loadingConfig}
            />
            {budgetType === 'absolute' ? (
              <p className="mt-1 text-[11px] text-slate-500">1 = INR 1 Mn</p>
            ) : null}
          </div>
        </div>
        <div className="mt-2 rounded-lg border border-slate-200 bg-slate-50 p-2.5">
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Initial Total Budget (Reference)</p>
          <p className="mt-1 text-sm font-semibold text-dark-text">
            {step1BaselineLoading ? 'Loading...' : formatCurrencyBn(step1BaselineBudget)}
          </p>
        </div>
      </div>
    )
  }

  function renderSetupForm(idPrefix: string) {
    const step2InputPreview = getStep2BudgetInput()
    return (
      <form className="space-y-2.5" onSubmit={handleGenerateScenarios}>
        <div className="flex flex-wrap items-center gap-2">
          <div className="rounded-full border border-primary/25 bg-primary/5 px-2.5 py-1">
            <p className="text-[11px] font-semibold uppercase tracking-wide text-primary">1. Brand</p>
          </div>
          <div className="rounded-full border border-primary/25 bg-primary/5 px-2.5 py-1">
            <p className="text-[11px] font-semibold uppercase tracking-wide text-primary">2. Intent + Markets</p>
          </div>
          <div className="rounded-full border border-primary/25 bg-primary/5 px-2.5 py-1">
            <p className="text-[11px] font-semibold uppercase tracking-wide text-primary">3. Constraints</p>
          </div>
        </div>

        <div className="rounded-xl border border-slate-200 bg-slate-50 p-3">
          <div className="grid gap-3 xl:grid-cols-[300px_minmax(0,1fr)]">
            <div className="rounded-lg border border-slate-200 bg-white p-3">
              <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Step 1</p>
              <label className="mt-2 block text-xs font-semibold uppercase tracking-wide text-slate-500" htmlFor={`${idPrefix}-brand`}>
                Brand
              </label>
              <select
                id={`${idPrefix}-brand`}
                value={selectedBrand}
                onChange={(event) => setSelectedBrand(event.target.value)}
                className="mt-1 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-700 focus:border-[#2563EB] focus:outline-none focus:ring-2 focus:ring-blue-200"
                disabled={loadingConfig}
              >
                {step2BrandOptions.map((brand) => (
                  <option key={brand} value={brand}>
                    {brand}
                  </option>
                ))}
              </select>
              <div className="mt-2 rounded-md border border-slate-200 bg-slate-50 px-2.5 py-2">
                <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">Budget From Step 1</p>
                <p className="mt-1 text-sm font-semibold text-dark-text">
                  {selectedBrandAllocation ? formatCurrencyBn(selectedBrandAllocation.allocated_budget) : '-'}
                </p>
                <p className="mt-0.5 text-xs text-slate-500">
                  Applied:{' '}
                  {step2InputPreview.budget_increase_type === 'absolute'
                    ? formatSignedCurrencyMn(step2InputPreview.budget_increase_value)
                    : formatSignedPct(step2InputPreview.budget_increase_value)}
                </p>
              </div>
            </div>

            <div className="rounded-lg border border-slate-200 bg-white p-3">
              <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Step 2</p>
              <div className="mt-2 grid gap-3 lg:grid-cols-[minmax(0,1fr)_320px]">
                <div>
                  <label
                    className="block text-xs font-semibold uppercase tracking-wide text-slate-500"
                    htmlFor={`${idPrefix}-scenario-intent`}
                  >
                    AI Intent
                  </label>
                  <textarea
                    id={`${idPrefix}-scenario-intent`}
                    rows={2}
                    value={scenarioIntent}
                    onChange={(event) => setScenarioIntent(event.target.value)}
                    placeholder="Example: Protect revenue while keeping volume growth positive."
                    className="mt-1 w-full resize-none rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-700 focus:border-[#2563EB] focus:outline-none focus:ring-2 focus:ring-blue-200"
                  />
                </div>

                <div ref={marketDropdownRef} className="relative">
                  <div className="flex items-center justify-between gap-2">
                    <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Market Selection</p>
                    <div className="flex items-center gap-2">
                      <button
                        type="button"
                        onClick={() => setSelectedMarkets(availableMarkets)}
                        className="rounded-lg border border-slate-300 bg-white px-2 py-1 text-[11px] font-semibold text-slate-700"
                      >
                        Select All
                      </button>
                      <button
                        type="button"
                        onClick={() => setSelectedMarkets([])}
                        className="rounded-lg border border-slate-300 bg-white px-2 py-1 text-[11px] font-semibold text-slate-700"
                      >
                        Clear
                      </button>
                    </div>
                  </div>
                  <button
                    type="button"
                    onClick={() => setMarketDropdownOpen((prev) => !prev)}
                    className="mt-1 flex w-full items-center justify-between rounded-lg border border-slate-300 bg-white px-3 py-2 text-left text-sm text-slate-700 focus:border-[#2563EB] focus:outline-none focus:ring-2 focus:ring-blue-200"
                  >
                    <span className="truncate">
                      {selectedMarkets.length > 0
                        ? `${selectedMarkets.length} markets selected`
                        : 'Select markets'}
                    </span>
                    <ChevronDown className={`h-4 w-4 text-slate-500 transition-transform ${marketDropdownOpen ? 'rotate-180' : ''}`} />
                  </button>

                  {marketDropdownOpen ? (
                    <div className="absolute z-20 mt-1 w-full rounded-lg border border-slate-200 bg-white p-2 shadow-lg">
                      <input
                        type="text"
                        value={marketSearch}
                        onChange={(event) => setMarketSearch(event.target.value)}
                        placeholder="Search market..."
                        className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-700 focus:border-[#2563EB] focus:outline-none focus:ring-2 focus:ring-blue-200"
                      />
                      <div className="mt-2 max-h-44 overflow-y-auto space-y-1 pr-1">
                        {filteredMarkets.map((market) => (
                          <label
                            key={`market-dropdown-${market}`}
                            className={`flex cursor-pointer items-center justify-between rounded-md border px-2.5 py-1.5 text-sm ${
                              selectedMarkets.includes(market)
                                ? 'border-primary/30 bg-primary/10 text-primary'
                                : 'border-slate-200 bg-white text-slate-700'
                            }`}
                          >
                            <span className="truncate pr-2">{market}</span>
                            <input
                              type="checkbox"
                              checked={selectedMarkets.includes(market)}
                              onChange={() => toggleMarket(market)}
                              className="h-4 w-4 rounded border-slate-300 text-primary focus:ring-blue-200"
                            />
                          </label>
                        ))}
                        {filteredMarkets.length === 0 ? (
                          <div className="rounded-md border border-slate-200 bg-slate-50 px-2.5 py-2 text-xs text-slate-500">
                            {selectedBrand ? 'No markets found.' : 'No markets mapped for this brand.'}
                          </div>
                        ) : null}
                      </div>
                    </div>
                  ) : null}
                </div>
              </div>
            </div>
          </div>
        </div>

        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Step 3</p>
          <p className="mt-0.5 text-xs text-slate-500">Edit market-level constraints before running scenario generation.</p>
          <div className="mt-2">{renderConstraintsPanel()}</div>
        </div>

        <div className="flex flex-wrap gap-2">
          <button
            type="submit"
            disabled={!canSubmit || scenarioStatus === 'queued' || scenarioStatus === 'running'}
            className="flex-1 rounded-lg bg-primary px-4 py-2.5 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:bg-slate-400"
          >
            {isSubmitting || scenarioStatus === 'queued' || scenarioStatus === 'running'
              ? 'Generating...'
              : 'Generate Scenarios'}
          </button>
          <button
            type="button"
            onClick={() => {
              setMarketSearch('')
              setSelectedMarkets(availableMarkets)
              setScenarioIntent('')
              setScenarioJobId('')
              setScenarioStatus('idle')
              setScenarioProgress(0)
              setScenarioMessage('')
              setScenarioStartedAt(null)
              setScenarioElapsedMs(0)
              setScenarioResults(null)
              setSelectedScenarioId('')
              setScenarioError('')
              setScenarioMinRevenuePct('')
              setScenarioMaxBudgetUtilizedPctFilter('')
            }}
            className="rounded-lg border border-slate-300 bg-white px-4 py-2.5 text-sm font-semibold text-slate-700"
          >
            Reset
          </button>
        </div>

        {errorMessage || scenarioError ? (
          <div className="rounded-lg border border-danger/20 bg-danger/10 px-3 py-2 text-sm text-danger">
            {scenarioError || errorMessage}
          </div>
        ) : null}
      </form>
    )
  }

  function renderSCurvesSection() {
    const tvPoints = sCurvesData?.curves.tv ?? []
    const dgPoints = sCurvesData?.curves.digital ?? []
    const activeMarketIndex = Math.max(0, sCurveStates.indexOf(activeSCurveState))
    const baselineTvReach = sCurvesData?.summary.baseline_tv_reach
    const baselineDigitalReach = sCurvesData?.summary.baseline_digital_reach
    const formatMnFromRaw = (value?: number | null) =>
      value == null || Number.isNaN(value) ? '-' : `${formatRawNumber(value / 100_000)}`
    const formatMn = (value?: number | null) =>
      value == null || Number.isNaN(value) ? '-' : `${formatRawNumber(value * 10)}`
    const getPointX = (point: SCurvePoint, xKey: 'tv_reach' | 'digital_reach') => {
      const raw = xKey === 'tv_reach' ? point.tv_reach : point.digital_reach
      const parsed = Number(raw)
      if (Number.isFinite(parsed) && parsed > 0) return parsed
      const base = xKey === 'tv_reach' ? Number(baselineTvReach) : Number(baselineDigitalReach)
      if (Number.isFinite(base) && base > 0) {
        const scale = Number(point.scale)
        if (Number.isFinite(scale) && scale > 0) return base * scale
        return base * (1 + Number(point.pct_change_input) / 100)
      }
      return 0
    }
    const getCurveBounds = (
      points: SCurvePoint[],
      xKey: 'tv_reach' | 'digital_reach',
      minReach?: number,
      maxReach?: number,
    ) => {
      if (points.length === 0) return null
      const sorted = [...points].sort((a, b) => getPointX(a, xKey) - getPointX(b, xKey))
      const firstX = getPointX(sorted[0], xKey)
      const lastX = getPointX(sorted[sorted.length - 1], xKey)
      const lowerTarget = Number.isFinite(minReach ?? NaN) ? Number(minReach) : firstX
      const upperTarget = Number.isFinite(maxReach ?? NaN) ? Number(maxReach) : lastX
      const midpointTarget = lowerTarget + (upperTarget - lowerTarget) / 2
      const nearestByX = (target: number) =>
        sorted.reduce((best, curr) =>
          Math.abs(getPointX(curr, xKey) - target) < Math.abs(getPointX(best, xKey) - target) ? curr : best,
        )
      const lower = nearestByX(lowerTarget)
      const midpoint = nearestByX(midpointTarget)
      const upper = nearestByX(upperTarget)
      return { lower, midpoint, upper, lowerTarget, midpointTarget, upperTarget }
    }
    const tvBounds = getCurveBounds(
      tvPoints,
      'tv_reach',
      sCurvesData?.summary.tv_min_reach,
      sCurvesData?.summary.tv_max_reach,
    )
    const dgBounds = getCurveBounds(
      dgPoints,
      'digital_reach',
      sCurvesData?.summary.digital_min_reach,
      sCurvesData?.summary.digital_max_reach,
    )

    const renderCurveCard = (
      title: string,
      color: string,
      points: SCurvePoint[],
      bounds: ReturnType<typeof getCurveBounds>,
      keyPrefix: string,
      xKey: 'tv_reach' | 'digital_reach',
      xLabel: string,
    ) => {
      if (points.length === 0 || !bounds) {
        return (
          <div className="rounded-lg border border-slate-200 bg-white p-3">
            <p className="text-sm font-semibold text-dark-text">{title}</p>
            <p className="mt-2 text-xs text-slate-500">No curve points available.</p>
          </div>
        )
      }

      const chartWidth = 620
      const chartHeight = 280
      const left = 56
      const right = 20
      const top = 16
      const bottom = 42
      const plotWidth = chartWidth - left - right
      const plotHeight = chartHeight - top - bottom
      const xMinRaw = Math.min(...points.map((p) => getPointX(p, xKey)))
      const xMaxRaw = Math.max(...points.map((p) => getPointX(p, xKey)))
      const yMinRaw = Math.min(...points.map((p) => p.predicted_volume))
      const yMaxRaw = Math.max(...points.map((p) => p.predicted_volume))
      const xPad = Math.max(2, (xMaxRaw - xMinRaw) * 0.06)
      const yPad = Math.max(0.4, (yMaxRaw - yMinRaw) * 0.12)
      const xMin = xMinRaw - xPad
      const xMax = xMaxRaw + xPad
      const yMin = yMinRaw - yPad
      const yMax = yMaxRaw + yPad
      const mapX = (x: number) => left + ((x - xMin) / Math.max(1e-9, xMax - xMin)) * plotWidth
      const mapY = (y: number) => top + ((yMax - y) / Math.max(1e-9, yMax - yMin)) * plotHeight
      const path = points
        .map((p, idx) => `${idx === 0 ? 'M' : 'L'} ${mapX(getPointX(p, xKey)).toFixed(2)} ${mapY(p.predicted_volume).toFixed(2)}`)
        .join(' ')
      const firstX = mapX(getPointX(points[0], xKey))
      const lastX = mapX(getPointX(points[points.length - 1], xKey))
      const areaPath = `${path} L ${lastX.toFixed(2)} ${(chartHeight - bottom).toFixed(2)} L ${firstX.toFixed(2)} ${(chartHeight - bottom).toFixed(2)} Z`
      const fy25Point = points.reduce((best, curr) =>
        Math.abs(curr.pct_change_input) < Math.abs(best.pct_change_input) ? curr : best,
      )
      const fy25Reach = getPointX(fy25Point, xKey)
      const fy25Vol = fy25Point.predicted_volume
      const lowerReach = Number(bounds.lowerTarget ?? getPointX(bounds.lower, xKey))
      const upperReach = Number(bounds.upperTarget ?? getPointX(bounds.upper, xKey))

      return (
        <div className="rounded-lg border border-slate-200 bg-white p-3 shadow-sm">
          <div className="flex items-center justify-between gap-2 border-b border-slate-100 pb-2">
            <p className="text-sm font-semibold text-dark-text">{title}</p>
            <span className="inline-flex items-center gap-1 rounded-full border border-slate-200 bg-slate-50 px-2 py-0.5 text-xs text-slate-600">
              <span className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: color }} />
              Predicted Volume
            </span>
          </div>
          <div className="mt-3 grid gap-2 text-xs text-slate-700 sm:grid-cols-3">
            <p className="rounded-md border border-slate-200 bg-slate-50 px-2 py-1.5 leading-relaxed">
              <span className="font-semibold text-slate-500">Min:</span> Reach {formatMnFromRaw(lowerReach)} Lakh | Vol {formatMnFromRaw(bounds.lower.predicted_volume)} Lakh
            </p>
            <p className="rounded-md border border-amber-200 bg-amber-50 px-2 py-1.5 leading-relaxed">
              <span className="font-semibold text-amber-700">FY25 Avg:</span> Reach {formatMnFromRaw(fy25Reach)} Lakh | Vol {formatMnFromRaw(fy25Vol)} Lakh
            </p>
            <p className="rounded-md border border-slate-200 bg-slate-50 px-2 py-1.5 leading-relaxed">
              <span className="font-semibold text-slate-500">Max:</span> Reach {formatMnFromRaw(upperReach)} Lakh | Vol {formatMnFromRaw(bounds.upper.predicted_volume)} Lakh
            </p>
          </div>
          <div className="mt-3 overflow-x-auto rounded-lg border border-slate-200 bg-slate-50/70 p-2">
            <svg
              width="100%"
              viewBox={`0 0 ${chartWidth} ${chartHeight}`}
              preserveAspectRatio="xMidYMid meet"
              role="img"
              aria-label={`${title} chart`}
            >
              {[0, 1, 2].map((i) => {
                const yVal = yMin + ((yMax - yMin) * i) / 2
                const y = mapY(yVal)
                return (
                  <g key={`${keyPrefix}-y-${i}`}>
                    <line x1={left} y1={y} x2={chartWidth - right} y2={y} stroke="#E2E8F0" strokeDasharray="3 3" />
                    <text x={left - 8} y={y + 4} textAnchor="end" fontSize="10" fill="#64748B">{formatMnFromRaw(yVal)}</text>
                  </g>
                )
              })}
              {[0, 1, 2].map((i) => {
                const xVal = xMin + ((xMax - xMin) * i) / 2
                const x = mapX(xVal)
                return (
                  <g key={`${keyPrefix}-x-${i}`}>
                    <line x1={x} y1={top} x2={x} y2={chartHeight - bottom} stroke="#E2E8F0" strokeDasharray="3 3" />
                    <text x={x} y={chartHeight - 14} textAnchor="middle" fontSize="10" fill="#64748B">{formatMnFromRaw(xVal)}</text>
                  </g>
                )
              })}
              <text x={chartWidth / 2} y={chartHeight - 2} textAnchor="middle" fontSize="11" fontWeight="700" fill="#334155">
                {xLabel} (Lakh)
              </text>
              <text transform={`translate(12 ${chartHeight / 2}) rotate(-90)`} textAnchor="middle" fontSize="11" fontWeight="700" fill="#334155">
                Predicted Volume (Lakh)
              </text>
              {[
                { label: 'Min', point: bounds.lower, reach: lowerReach, stroke: '#64748B', dash: '2 4' },
                { label: 'Max', point: bounds.upper, reach: upperReach, stroke: '#64748B', dash: '2 4' },
              ].map((marker) => (
                <g key={`${keyPrefix}-${marker.label}`}>
                  <line
                    x1={mapX(marker.reach)}
                    y1={top}
                    x2={mapX(marker.reach)}
                    y2={chartHeight - bottom}
                    stroke={marker.stroke}
                    strokeDasharray={marker.dash}
                    strokeWidth={1}
                    opacity={0.65}
                  />
                  <circle cx={mapX(marker.reach)} cy={mapY(marker.point.predicted_volume)} r="3.5" fill={marker.stroke} />
                  <text x={mapX(marker.reach) + 6} y={mapY(marker.point.predicted_volume) - 6} textAnchor="start" fontSize="10" fontWeight="700" fill={marker.stroke}>
                    {marker.label}
                  </text>
                </g>
              ))}
              <line
                x1={mapX(fy25Reach)}
                y1={top}
                x2={mapX(fy25Reach)}
                y2={chartHeight - bottom}
                stroke="#2563EB"
                strokeDasharray="5 4"
                strokeWidth="1.6"
              />
              <circle cx={mapX(fy25Reach)} cy={mapY(fy25Vol)} r="4.2" fill="#2563EB" stroke="#FFFFFF" strokeWidth="1.2" />
              <text x={mapX(fy25Reach) + 8} y={mapY(fy25Vol) - 8} textAnchor="start" fontSize="10" fontWeight="700" fill="#1D4ED8">
                FY25 Avg
              </text>
              <path d={areaPath} fill={color} opacity="0.12" />
              <path d={path} fill="none" stroke={color} strokeWidth="2.8" strokeLinecap="round" />
            </svg>
          </div>
        </div>
      )
    }
    const contributionItems = contributionData?.items ?? []
    const contributionAbsMax = Math.max(1, ...contributionItems.map((item) => Math.abs(item.absolute_contribution)))
    const contributionPctMax = Math.max(1, ...contributionItems.map((item) => Math.abs(item.share_pct)))
    const renderContributionCard = (title: string, mode: 'absolute' | 'share') => (
      <div className="rounded-lg border border-slate-200 bg-white p-3 shadow-sm">
        <div className="flex items-center justify-between border-b border-slate-100 pb-2">
          <p className="text-sm font-semibold text-dark-text">{title}</p>
          <span className="text-xs text-slate-500">
            {contributionData?.selection.fiscal_year ? `FY ${contributionData.selection.fiscal_year}` : 'Latest FY'}
          </span>
        </div>
        <div className="mt-3 space-y-2.5">
          {contributionItems.length === 0 ? (
            <p className="text-xs text-slate-500">No contribution data available.</p>
          ) : (
            contributionItems.map((item) => {
              const value = mode === 'absolute' ? item.absolute_contribution : item.share_pct
              const widthPct =
                ((Math.abs(value) / (mode === 'absolute' ? contributionAbsMax : contributionPctMax)) * 100).toFixed(1)
              const isPositive = value >= 0
                return (
                  <div key={`${mode}-${item.variable}`} className="space-y-1">
                    <div className="flex items-center justify-between gap-2">
                      <p className="truncate text-xs font-medium text-slate-700">{item.label}</p>
                      <p className={`text-xs font-semibold ${isPositive ? 'text-primary' : 'text-danger'}`}>
                        {mode === 'absolute' ? `${formatMn(value / 1_000_000)} Lakh` : formatSignedPct(value, 2)}
                      </p>
                    </div>
                  <div className="h-2.5 rounded-full bg-slate-100">
                    <div
                      className={`h-2.5 rounded-full ${isPositive ? 'bg-primary/80' : 'bg-danger/75'}`}
                      style={{ width: `${widthPct}%` }}
                    />
                  </div>
                </div>
              )
            })
          )}
        </div>
      </div>
    )
    const renderYoyGrowthCard = () => {
      const points = yoyData?.items ?? []
      const wf = yoyData?.waterfall
      if (points.length === 0 || !wf || wf.items.length === 0) {
        return (
          <div className="rounded-lg border border-slate-200 bg-white p-3 shadow-sm">
            <p className="text-sm font-semibold text-dark-text">YoY Bridge</p>
            <p className="mt-2 text-xs text-slate-500">No YoY data available.</p>
          </div>
        )
      }
      const fromPoint = points.find((p) => p.fiscal_year === wf.from_fiscal_year)
      const toPoint = points.find((p) => p.fiscal_year === wf.to_fiscal_year)
      if (!fromPoint || !toPoint) {
        return (
          <div className="rounded-lg border border-slate-200 bg-white p-3 shadow-sm">
            <p className="text-sm font-semibold text-dark-text">YoY Bridge</p>
            <p className="mt-2 text-xs text-slate-500">Unable to render YoY bridge for this selection.</p>
          </div>
        )
      }

      const drivers = (wf.items ?? []).slice(0, 8).map((item) => ({
        ...item,
        label: item.label.replace(/AllMedia Reach/gi, 'Halo Media Reach').replace(/\s+/g, ' ').trim(),
      }))
      type BridgeStep = {
        key: string
        label: string
        type: 'start' | 'driver' | 'end'
        from: number
        to: number
        delta: number
        sharePct?: number
      }
      const steps: BridgeStep[] = []
      let running = fromPoint.volume_mn
      steps.push({
        key: `start-${wf.from_fiscal_year}`,
        label: wf.from_fiscal_year,
        type: 'start',
        from: 0,
        to: fromPoint.volume_mn,
        delta: fromPoint.volume_mn,
      })
      for (const item of drivers) {
        const next = running + item.delta_mn
        steps.push({
          key: `driver-${item.label}`,
          label: item.label,
          type: 'driver',
          from: running,
          to: next,
          delta: item.delta_mn,
          sharePct: Number(item.share_of_total_change_pct),
        })
        running = next
      }
      steps.push({
        key: `end-${wf.to_fiscal_year}`,
        label: wf.to_fiscal_year,
        type: 'end',
        from: 0,
        to: toPoint.volume_mn,
        delta: toPoint.volume_mn,
      })

      const minY = Math.min(0, ...steps.map((s) => Math.min(s.from, s.to)))
      const maxY = Math.max(...steps.map((s) => Math.max(s.from, s.to)))
      const yPad = Math.max(0.01, (maxY - minY) * 0.16)
      const yLow = minY - yPad
      const yHigh = maxY + yPad
      const chartHeight = 410
      const top = 22
      const bottom = 118
      const left = 56
      const right = 28
      const plotHeight = chartHeight - top - bottom
      const chartWidth = Math.max(1280, left + right + steps.length * 120)
      const slotWidth = (chartWidth - left - right) / Math.max(1, steps.length)
      const barWidth = Math.min(72, Math.max(44, slotWidth * 0.58))
      const mapY = (value: number) => top + ((yHigh - value) / Math.max(1e-9, yHigh - yLow)) * plotHeight
      const xFor = (idx: number) => left + idx * slotWidth + (slotWidth - barWidth) / 2
      const ticks = [0, 1, 2, 3]

      return (
        <div className="rounded-lg border border-slate-200 bg-white p-3 shadow-sm">
          <div className="flex items-center justify-between border-b border-slate-100 pb-2">
            <p className="text-sm font-semibold text-dark-text">YoY Bridge</p>
            <span className="text-xs text-slate-500">Start + driver impacts + end value. Share % is shown below each driver.</span>
          </div>
          <div className="mt-3 grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
            <div className="rounded-md border border-slate-200 bg-slate-50 px-3 py-2">
              <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">Start ({wf.from_fiscal_year})</p>
              <p className="mt-1 text-sm font-semibold text-dark-text">{(fromPoint.volume_mn * 10).toFixed(2)} Lakh</p>
            </div>
            <div className="rounded-md border border-slate-200 bg-slate-50 px-3 py-2">
              <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">End ({wf.to_fiscal_year})</p>
              <p className="mt-1 text-sm font-semibold text-dark-text">{(toPoint.volume_mn * 10).toFixed(2)} Lakh</p>
            </div>
            <div className="rounded-md border border-slate-200 bg-slate-50 px-3 py-2">
              <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">Net Change</p>
              <p className={`mt-1 text-sm font-semibold ${wf.total_change_mn >= 0 ? 'text-success' : 'text-danger'}`}>
                {formatSignedNumber((wf.total_change_mn ?? 0) * 10, 2)} Lakh
              </p>
            </div>
            <div className="rounded-md border border-slate-200 bg-slate-50 px-3 py-2">
              <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">YoY Growth</p>
              <p className={`mt-1 text-sm font-semibold ${(toPoint.yoy_growth_pct ?? 0) >= 0 ? 'text-success' : 'text-danger'}`}>
                {formatSignedPct(toPoint.yoy_growth_pct, 2)}
              </p>
            </div>
          </div>
          <div className="mt-3 overflow-x-auto rounded-lg border border-slate-200 bg-slate-50/70 p-2">
            <svg width={chartWidth} height={chartHeight} role="img" aria-label="YoY bridge chart">
              {ticks.map((i) => {
                const v = yLow + ((yHigh - yLow) * i) / (ticks.length - 1)
                const y = mapY(v)
                return (
                  <g key={`bridge-tick-${i}`}>
                    <line x1={left} y1={y} x2={chartWidth - right} y2={y} stroke="#E2E8F0" strokeDasharray="3 3" />
                    <text x={left - 12} y={y + 4} textAnchor="end" fontSize="10" fill="#64748B">
                      {formatRawNumber(v * 10)}
                    </text>
                  </g>
                )
              })}

              {steps.map((step, idx) => {
                const x = xFor(idx)
                const y0 = mapY(step.from)
                const y1 = mapY(step.to)
                const yTop = Math.min(y0, y1)
                const height = Math.max(1, Math.abs(y1 - y0))
                const isPositive = step.delta >= 0
                const isTotal = step.type === 'start' || step.type === 'end'
                const color = isTotal ? '#2563EB' : isPositive ? '#16A34A' : '#F97316'
                const valueLabel =
                  step.type === 'driver' ? `${step.delta >= 0 ? '+' : ''}${(step.delta * 10).toFixed(2)} Lakh` : `${(step.to * 10).toFixed(2)} Lakh`
                const shortLabel = step.label.length > 15 ? `${step.label.slice(0, 15)}...` : step.label
                const pctLabel = step.type === 'driver' && Number.isFinite(step.sharePct)
                  ? `${(step.sharePct ?? 0) >= 0 ? '+' : ''}${(step.sharePct ?? 0).toFixed(1)}%`
                  : ''
                return (
                  <g key={step.key}>
                    <rect x={x} y={yTop} width={barWidth} height={height} rx={4} fill={color} opacity={isTotal ? 0.85 : 0.92} />
                    <text x={x + barWidth / 2} y={yTop - 6} textAnchor="middle" fontSize="10" fontWeight="600" fill="#0F172A">
                      {valueLabel}
                    </text>
                    <text x={x + barWidth / 2} y={chartHeight - 38} textAnchor="middle" fontSize="10" fill="#334155">
                      {shortLabel}
                    </text>
                    {pctLabel ? (
                      <text x={x + barWidth / 2} y={chartHeight - 20} textAnchor="middle" fontSize="10" fontWeight="600" fill={isPositive ? '#16A34A' : '#F97316'}>
                        {pctLabel}
                      </text>
                    ) : null}
                    {idx < steps.length - 1 ? (
                      <line
                        x1={x + barWidth}
                        y1={mapY(step.to)}
                        x2={xFor(idx + 1)}
                        y2={mapY(step.to)}
                        stroke="#94A3B8"
                        strokeDasharray="4 3"
                      />
                    ) : null}
                  </g>
                )
              })}

              <text transform={`translate(14 ${chartHeight / 2}) rotate(-90)`} textAnchor="middle" fontSize="11" fontWeight="700" fill="#334155">
                Volume (Lakh)
              </text>
              <text x={chartWidth / 2} y={chartHeight - 4} textAnchor="middle" fontSize="11" fontWeight="700" fill="#334155">
                Drivers And Share Of Net Change (%)
              </text>
            </svg>
          </div>
        </div>
      )
    }

    return (
      <section className="rounded-xl border border-slate-200 bg-white p-4 shadow-panel sm:p-5">
        <div className="mb-3 flex items-center justify-between gap-3">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-primary">Insights</p>
            <h2 className="mt-1 text-lg font-semibold text-dark-text">S Curves & Contribution Drivers</h2>
            <p className="mt-1 text-sm text-slate-500">Navigate markets and review response curves, contribution drivers, and YoY growth for the selected state.</p>
            <p className="mt-1 text-xs font-semibold uppercase tracking-wide text-slate-500">All chart values are shown in lakhs</p>
          </div>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={openAiModeModal}
              disabled={!selectedBrand || loadingConfig}
              className="inline-flex items-center gap-2 rounded-lg bg-primary px-3 py-2 text-xs font-semibold text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:bg-slate-400"
            >
              <Bot className="h-4 w-4" />
              Trinity Mode
            </button>
            <button
              type="button"
              onClick={() => {
                void loadSCurves()
                void loadContributionInsights()
                void loadYoyGrowth()
              }}
              disabled={(sCurvesLoading || contributionLoading || yoyLoading) || !selectedBrand || !activeSCurveState}
              className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-xs font-semibold text-slate-700 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {(sCurvesLoading || contributionLoading || yoyLoading) ? 'Refreshing...' : 'Refresh Insights'}
            </button>
          </div>
        </div>

        <div className="grid gap-3 rounded-lg border border-slate-200 bg-slate-50 p-3 lg:grid-cols-[220px_minmax(0,1fr)]">
          <div className="rounded-lg border border-slate-200 bg-white p-3">
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">State Slider</p>
            <div className="mt-2 max-h-[420px] space-y-1 overflow-y-auto pr-1">
              {sCurveStates.map((market, idx) => (
                <button
                  key={`state-nav-${market}`}
                  type="button"
                  onClick={() => setSCurveStateIndex(idx)}
                  className={`w-full truncate rounded-md border px-2.5 py-1.5 text-left text-xs font-semibold ${
                    idx === activeMarketIndex
                      ? 'border-primary/30 bg-primary/10 text-primary'
                      : 'border-slate-200 bg-white text-slate-700'
                  }`}
                >
                  {market}
                </button>
              ))}
            </div>
          </div>
          <div className="space-y-3">
            <div>
              <label className="text-xs font-semibold uppercase tracking-wide text-slate-500">Brand</label>
              <select
                value={selectedBrand}
                onChange={(event) => setSelectedBrand(event.target.value)}
                className="mt-1 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-700 focus:border-[#2563EB] focus:outline-none focus:ring-2 focus:ring-blue-200"
                disabled={loadingConfig}
              >
                {step2BrandOptions.map((brand) => (
                  <option key={brand} value={brand}>
                    {brand}
                  </option>
                ))}
              </select>
            </div>
            <div className="inline-flex w-full rounded-lg border border-slate-200 bg-white p-1">
              <button
                type="button"
                onClick={() => setActiveInsightsSection('curves')}
                className={`flex-1 rounded-md px-3 py-2 text-xs font-semibold ${
                  activeInsightsSection === 'curves' ? 'bg-primary text-white' : 'text-slate-700'
                }`}
              >
                S Curves
              </button>
              <button
                type="button"
                onClick={() => setActiveInsightsSection('contribution')}
                className={`flex-1 rounded-md px-3 py-2 text-xs font-semibold ${
                  activeInsightsSection === 'contribution' ? 'bg-primary text-white' : 'text-slate-700'
                }`}
              >
                Contribution
              </button>
              <button
                type="button"
                onClick={() => setActiveInsightsSection('yoy')}
                className={`flex-1 rounded-md px-3 py-2 text-xs font-semibold ${
                  activeInsightsSection === 'yoy' ? 'bg-primary text-white' : 'text-slate-700'
                }`}
              >
                YoY Growth
              </button>
            </div>

            {activeInsightsSection === 'curves' && sCurvesError ? (
              <div className="rounded-lg border border-danger/20 bg-danger/10 px-3 py-2 text-sm text-danger">{sCurvesError}</div>
            ) : null}

            {activeInsightsSection === 'curves' && sCurvesLoading && !sCurvesData ? (
              <div className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-3 text-sm text-slate-600">Loading S-curves...</div>
            ) : null}

            {activeInsightsSection === 'curves' && !sCurvesLoading && sCurvesData ? (
              <div className="grid gap-3 xl:grid-cols-2">
                {renderCurveCard('TV S-Curve', '#2563EB', tvPoints, tvBounds, 'tv', 'tv_reach', 'TV Reach')}
                {renderCurveCard('Digital S-Curve', '#16A34A', dgPoints, dgBounds, 'dg', 'digital_reach', 'Digital Reach')}
              </div>
            ) : null}

            {activeInsightsSection === 'contribution' && contributionError ? (
              <div className="rounded-lg border border-danger/20 bg-danger/10 px-3 py-2 text-sm text-danger">{contributionError}</div>
            ) : null}

            {activeInsightsSection === 'contribution' && contributionLoading && !contributionData ? (
              <div className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-3 text-sm text-slate-600">Loading contribution drivers...</div>
            ) : null}

            {activeInsightsSection === 'contribution' && !contributionLoading && contributionData ? (
              <div className="grid gap-3 xl:grid-cols-2">
                {renderContributionCard('Contribution (Absolute)', 'absolute')}
                {renderContributionCard('Contribution Share (%)', 'share')}
              </div>
            ) : null}

            {activeInsightsSection === 'yoy' && yoyError ? (
              <div className="rounded-lg border border-danger/20 bg-danger/10 px-3 py-2 text-sm text-danger">{yoyError}</div>
            ) : null}

            {activeInsightsSection === 'yoy' && yoyLoading && !yoyData ? (
              <div className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-3 text-sm text-slate-600">Loading YoY growth...</div>
            ) : null}

            {activeInsightsSection === 'yoy' && !yoyLoading && yoyData ? renderYoyGrowthCard() : null}
          </div>
        </div>
      </section>
    )
  }

  function renderAiModeModal() {
    if (!aiModeOpen) return null
    const structured = aiModeData?.ai_structured ?? null
    const summaryJson = aiModeData?.ai_summary_json ?? structured?.summary_json ?? null
    const reportDate = new Date().toLocaleDateString('en-IN', {
      day: '2-digit',
      month: 'short',
      year: 'numeric',
    })

    const renderSummaryActionList = (
      title: string,
      tone: 'positive' | 'risk',
      rows: Array<{ state: string; channel: string; reason: string; action: string }>,
    ) => {
      const borderClass = tone === 'positive' ? 'border-success/30' : 'border-danger/30'
      const titleClass = tone === 'positive' ? 'text-success' : 'text-danger'
      const badgeClass = tone === 'positive' ? 'bg-success/10 text-success border-success/20' : 'bg-danger/10 text-danger border-danger/20'
      return (
        <div className={`rounded-xl border bg-white p-4 shadow-sm ${borderClass}`}>
          <p className={`text-xs font-semibold uppercase tracking-wide ${titleClass}`}>{title}</p>
          <div className="mt-3 space-y-2.5">
            {rows.length === 0 ? (
              <p className="text-sm text-slate-500">No specific states identified.</p>
            ) : (
              rows.map((row, index) => (
                <div key={`${title}-${row.state}-${index}`} className="rounded-lg border border-slate-200 bg-slate-50 p-3">
                  <div className="flex items-center justify-between gap-2">
                    <p className="text-sm font-semibold text-dark-text">{row.state}</p>
                    <span className={`rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide ${badgeClass}`}>
                      {row.channel}
                    </span>
                  </div>
                  <p className="mt-1 text-xs text-slate-600">
                    <span className="font-semibold text-slate-700">Why:</span> {row.reason}
                  </p>
                  <p className="mt-1 text-xs text-slate-600">
                    <span className="font-semibold text-slate-700">Action:</span> {row.action}
                  </p>
                </div>
              ))
            )}
          </div>
        </div>
      )
    }

    const renderMediaInvestmentFramework = () => {
      const items = aiModeData?.market_cards ?? []
      if (items.length === 0) return null
      const groups = {
        increase_media_investments: items.filter((x) => x.investment_quadrant === 'increase_media_investments'),
        maintain_high_salience: items.filter((x) => x.investment_quadrant === 'maintain_high_salience'),
        maintain_selective: items.filter((x) => x.investment_quadrant === 'maintain_selective'),
        scale_back: items.filter((x) => x.investment_quadrant === 'scale_back'),
      }
      const salienceCutoff = aiModeData?.investment_framework?.salience_threshold_pct
      const responsivenessCutoff = aiModeData?.investment_framework?.responsiveness_threshold_pct
      const renderGroup = (
        title: string,
        tone: 'green' | 'amber' | 'red',
        rows: AIInsightsMarketCard[],
      ) => {
        const theme =
          tone === 'green'
            ? 'border-success/30 bg-success/5 text-success'
            : tone === 'red'
              ? 'border-danger/30 bg-danger/5 text-danger'
              : 'border-amber-300 bg-amber-50 text-amber-700'
        return (
          <div className={`rounded-xl border p-4 ${theme}`}>
            <p className="text-xs font-semibold uppercase tracking-wide">{title}</p>
            <div className="mt-2 space-y-2">
              {rows.length === 0 ? (
                <p className="text-xs text-slate-600">No states in this quadrant.</p>
              ) : (
                rows.map((row) => (
                  <div key={`quad-${title}-${row.market}`} className="rounded-lg border border-slate-200 bg-white p-2.5 text-slate-700">
                    <p className="text-sm font-semibold text-dark-text">{row.market}</p>
                    <p className="mt-1 text-xs">
                      Salience {formatPct(row.category_salience_pct, 1)} | Responsiveness {formatPct(row.media_responsiveness_pct, 1)} | {row.leader_position || '-'}
                    </p>
                  </div>
                ))
              )}
            </div>
          </div>
        )
      }
      return (
        <div className="rounded-xl border border-slate-200 bg-white p-4">
          <p className="text-xs font-semibold uppercase tracking-wide text-primary">Media Investment Framework</p>
          <p className="mt-1 text-xs text-slate-500">
            Salience cutoff: {formatPct(salienceCutoff, 1)} | Responsiveness cutoff: {formatPct(responsivenessCutoff, 1)}
          </p>
          <div className="mt-3 grid gap-3 xl:grid-cols-2">
            {renderGroup('Increase Media Investments', 'green', groups.increase_media_investments)}
            {renderGroup('Maintain (High Salience)', 'amber', groups.maintain_high_salience)}
            {renderGroup('Maintain (Selective)', 'amber', groups.maintain_selective)}
            {renderGroup('Scale Back', 'red', groups.scale_back)}
          </div>
        </div>
      )
    }

    const userFacingNotes = (aiModeData?.notes ?? [])
      .map((note) => {
        const low = note.toLowerCase()
        if (low.includes('429') || low.includes('rate limit')) return 'AI service is rate-limited right now. Deterministic report logic has been used.'
        if (low.includes('api key missing')) return 'AI key not configured. Deterministic report logic has been used.'
        if (low.includes('fallback') || low.includes('deterministic')) return 'Fallback report logic was applied for this run.'
        return note
      })
      .filter((note, index, arr) => arr.indexOf(note) === index)

    return (
      <div className="fixed inset-0 z-50">
        <button type="button" aria-label="Close Trinity Mode" className="absolute inset-0 bg-slate-900/45" onClick={closeAiModeModal} />
        <div className="absolute inset-0 p-3 sm:p-6">
          <div className="mx-auto flex h-[92vh] w-[96vw] max-w-[1560px] overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-2xl">
            <aside className="w-full max-w-sm flex-shrink-0 border-r border-slate-200 bg-slate-50/70 p-5">
              <div className="flex items-center justify-between gap-3 border-b border-slate-200 pb-3">
                <div className="flex items-center gap-2">
                  <div className="rounded-lg bg-primary/10 p-2 text-primary">
                    <Bot className="h-4 w-4" />
                  </div>
                  <div>
                    <p className="text-xs font-semibold uppercase tracking-wide text-primary">Trinity Mode</p>
                    <h3 className="text-base font-semibold text-dark-text">Brand Intelligence Report</h3>
                  </div>
                </div>
                <button
                  type="button"
                  onClick={closeAiModeModal}
                  className="rounded-lg border border-slate-300 bg-white p-1.5 text-slate-600 hover:bg-slate-100"
                >
                  <X className="h-4 w-4" />
                </button>
              </div>

              <div className="mt-4 space-y-4">
                <div>
                  <label className="text-xs font-semibold uppercase tracking-wide text-slate-500">Brand</label>
                  <select
                    value={aiModeBrand}
                    onChange={(event) => setAiModeBrand(event.target.value)}
                    className="mt-1 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-700 focus:border-[#2563EB] focus:outline-none focus:ring-2 focus:ring-blue-200"
                  >
                    {step2BrandOptions.map((brand) => (
                      <option key={`ai-mode-brand-${brand}`} value={brand}>
                        {brand}
                      </option>
                    ))}
                  </select>
                </div>

                <div className="rounded-lg border border-slate-200 bg-white p-3">
                  <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Coverage</p>
                  <p className="mt-1 text-sm font-semibold text-dark-text">{aiModeMarkets.length} Markets</p>
                  <p className="mt-1 text-xs text-slate-500">Trinity auto-summarizes S-Curves, contribution drivers, and YoY signals into a business-ready report.</p>
                </div>

                <button
                  type="button"
                  onClick={() => void handleGenerateAiInsights()}
                  disabled={aiModeLoading || !aiModeBrand || aiModeMarkets.length === 0}
                  className="w-full rounded-lg bg-primary px-4 py-2.5 text-sm font-semibold text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:bg-slate-400"
                >
                  {aiModeLoading ? 'Generating Report...' : 'Generate Trinity Report'}
                </button>

                {aiModeError ? (
                  <div className="rounded-lg border border-danger/20 bg-danger/10 px-3 py-2 text-sm text-danger">{aiModeError}</div>
                ) : null}
              </div>
            </aside>

            <section className="flex-1 overflow-y-auto bg-white p-5 sm:p-6">
              {!aiModeData && !aiModeLoading ? (
                <div className="flex h-full items-center justify-center rounded-xl border border-dashed border-slate-300 bg-slate-50">
                  <div className="max-w-md text-center">
                    <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Trinity Report Output</p>
                    <p className="mt-2 text-base font-semibold text-dark-text">Generate a polished brand report for the selected brand.</p>
                    <p className="mt-2 text-sm text-slate-600">You will get executive summary, state clustering, recommendations, and action priorities.</p>
                  </div>
                </div>
              ) : null}

              {aiModeLoading ? (
                <div className="space-y-3">
                  <div className="h-16 animate-pulse rounded-xl border border-slate-200 bg-slate-100" />
                  <div className="h-36 animate-pulse rounded-xl border border-slate-200 bg-slate-100" />
                  <div className="h-56 animate-pulse rounded-xl border border-slate-200 bg-slate-100" />
                </div>
              ) : null}

              {!aiModeLoading && aiModeData ? (
                <div className="space-y-4">
                  <div className="rounded-xl border border-slate-200 bg-slate-50 p-4">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <p className="text-xs font-semibold uppercase tracking-wide text-primary">Trinity Brand Report</p>
                      <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Generated: {reportDate}</p>
                    </div>
                    <h4 className="mt-2 text-lg font-semibold text-dark-text">
                      {summaryJson?.headline || `${aiModeData.selection.brand} Portfolio Intelligence`}
                    </h4>
                    <p className="mt-1 text-sm text-slate-600">
                      Auto-generated strategic summary from market response curves, contribution signals, and YoY movement.
                    </p>
                  </div>

                  <div className="grid gap-3 xl:grid-cols-5">
                    <div className="rounded-xl border border-slate-200 bg-slate-50 p-3">
                      <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Brand</p>
                      <p className="mt-1 text-base font-semibold text-dark-text">{aiModeData.selection.brand}</p>
                    </div>
                    <div className="rounded-xl border border-slate-200 bg-slate-50 p-3">
                      <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">States Covered</p>
                      <p className="mt-1 text-base font-semibold text-dark-text">{aiModeData.selection.markets_count}</p>
                    </div>
                    <div className="rounded-xl border border-slate-200 bg-slate-50 p-3">
                      <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Positive YoY States</p>
                      <p className="mt-1 text-base font-semibold text-dark-text">
                        {aiModeData.portfolio_metrics?.positive_yoy_states ?? '-'}
                      </p>
                    </div>
                    <div className="rounded-xl border border-slate-200 bg-slate-50 p-3">
                      <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Average YoY</p>
                      <p className={`mt-1 text-base font-semibold ${(aiModeData.portfolio_metrics?.avg_yoy_growth_pct ?? 0) >= 0 ? 'text-success' : 'text-danger'}`}>
                        {formatSignedPct(aiModeData.portfolio_metrics?.avg_yoy_growth_pct, 2)}
                      </p>
                    </div>
                    <div className="rounded-xl border border-slate-200 bg-slate-50 p-3">
                      <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Engine</p>
                      <p className="mt-1 text-sm font-semibold uppercase text-dark-text">{aiModeData.summary.provider}</p>
                    </div>
                  </div>

                  <div className="rounded-xl border border-slate-200 bg-white p-4">
                    <p className="text-xs font-semibold uppercase tracking-wide text-primary">Signals Used For Trinity Report</p>
                    <div className="mt-3 grid gap-3 xl:grid-cols-3">
                      <div className="rounded-lg border border-slate-200 bg-slate-50 p-3">
                        <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">YoY Signal</p>
                        <p className="mt-1 text-sm text-slate-700">
                          {aiModeData.signal_snapshot?.yoy?.latest_fiscal_year || '-'} |{' '}
                          {formatSignedPct(aiModeData.signal_snapshot?.yoy?.latest_yoy_growth_pct, 2)}
                        </p>
                        <p className="mt-1 text-xs text-slate-500">
                          Volume: {formatRawNumber(aiModeData.signal_snapshot?.yoy?.latest_volume_mn)} Mn
                        </p>
                      </div>
                      <div className="rounded-lg border border-slate-200 bg-slate-50 p-3">
                        <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">S-Curve Signal</p>
                        <p className="mt-1 text-xs text-slate-600">
                          TV uplift band: {formatSignedPct(aiModeData.signal_snapshot?.s_curve?.tv_first_uplift_pct, 1)} to {formatSignedPct(aiModeData.signal_snapshot?.s_curve?.tv_last_uplift_pct, 1)}
                        </p>
                        <p className="mt-1 text-xs text-slate-600">
                          Digital uplift band: {formatSignedPct(aiModeData.signal_snapshot?.s_curve?.dg_first_uplift_pct, 1)} to {formatSignedPct(aiModeData.signal_snapshot?.s_curve?.dg_last_uplift_pct, 1)}
                        </p>
                      </div>
                      <div className="rounded-lg border border-slate-200 bg-slate-50 p-3">
                        <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">Top Contribution Drivers</p>
                        <div className="mt-1 space-y-1">
                          {(aiModeData.signal_snapshot?.contribution_top ?? []).slice(0, 3).map((item, idx) => (
                            <p key={`signal-driver-${idx}`} className="text-xs text-slate-700">
                              {item.variable}: {formatSignedPct(item.share_pct, 1)}
                            </p>
                          ))}
                          {(aiModeData.signal_snapshot?.contribution_top ?? []).length === 0 ? (
                            <p className="text-xs text-slate-500">No contribution context passed for this run.</p>
                          ) : null}
                        </div>
                      </div>
                    </div>
                  </div>

                  {structured ? (
                    <>
                      <div className="rounded-xl border border-slate-200 bg-white p-4">
                        <p className="text-xs font-semibold uppercase tracking-wide text-primary">Executive Summary</p>
                        <p className="mt-2 text-sm leading-relaxed text-slate-700">
                          {summaryJson?.portfolio_takeaway || aiModeData.computed_executive_summary || structured.executive_summary || '-'}
                        </p>
                        <p className="mt-3 text-xs font-semibold uppercase tracking-wide text-slate-500">YoY Position</p>
                        <p className="mt-2 text-sm leading-relaxed text-slate-700">{structured.portfolio_position}</p>
                      </div>

                      {(summaryJson?.risks?.length ?? 0) > 0 || (summaryJson?.evidence?.length ?? 0) > 0 ? (
                        <div className="grid gap-3 xl:grid-cols-2">
                          <div className="rounded-xl border border-amber-300 bg-amber-50 p-4">
                            <p className="text-xs font-semibold uppercase tracking-wide text-amber-700">Key Risks</p>
                            <div className="mt-2 space-y-1.5">
                              {(summaryJson?.risks ?? []).map((risk, idx) => (
                                <p key={`risk-${idx}`} className="text-sm text-slate-700">{risk}</p>
                              ))}
                            </div>
                          </div>
                          <div className="rounded-xl border border-slate-200 bg-slate-50 p-4">
                            <p className="text-xs font-semibold uppercase tracking-wide text-slate-600">Evidence</p>
                            <div className="mt-2 space-y-1.5">
                              {(summaryJson?.evidence ?? []).map((item, idx) => (
                                <p key={`evidence-${idx}`} className="text-sm text-slate-700">{item}</p>
                              ))}
                            </div>
                          </div>
                        </div>
                      ) : null}

                      <div className="grid gap-3 xl:grid-cols-3">
                        <div className="rounded-xl border border-success/35 bg-success/5 p-4">
                          <p className="text-xs font-semibold uppercase tracking-wide text-success">Champion States</p>
                          <p className="mt-2 text-sm font-semibold text-dark-text">
                            {aiModeData.state_clusters.growth_leaders.length
                              ? aiModeData.state_clusters.growth_leaders.join(', ')
                              : 'No clear champions identified'}
                          </p>
                        </div>
                        <div className="rounded-xl border border-slate-200 bg-slate-50 p-4">
                          <p className="text-xs font-semibold uppercase tracking-wide text-slate-600">Stable Core</p>
                          <p className="mt-2 text-sm font-semibold text-dark-text">
                            {aiModeData.state_clusters.stable_core.length
                              ? aiModeData.state_clusters.stable_core.join(', ')
                              : 'No stable-core states identified'}
                          </p>
                        </div>
                        <div className="rounded-xl border border-amber-300 bg-amber-50 p-4">
                          <p className="text-xs font-semibold uppercase tracking-wide text-amber-700">Laggard States</p>
                          <p className="mt-2 text-sm font-semibold text-dark-text">
                            {aiModeData.state_clusters.recovery_priority.length
                              ? aiModeData.state_clusters.recovery_priority.join(', ')
                              : 'No laggard states identified'}
                          </p>
                        </div>
                      </div>

                      {renderMediaInvestmentFramework()}

                      <div className="grid gap-3 xl:grid-cols-2">
                        <div className="rounded-xl border border-slate-200 bg-white p-4">
                          <p className="text-xs font-semibold uppercase tracking-wide text-primary">TV Effectiveness</p>
                          <p className="mt-2 text-xs font-semibold uppercase tracking-wide text-slate-500">Working States</p>
                          <p className="mt-1 text-sm text-slate-700">
                            {aiModeData.channel_diagnostics?.tv.working_states?.length
                              ? aiModeData.channel_diagnostics.tv.working_states.join(', ')
                              : '-'}
                          </p>
                          <p className="mt-3 text-xs font-semibold uppercase tracking-wide text-slate-500">Needs Attention</p>
                          <p className="mt-1 text-sm text-slate-700">
                            {aiModeData.channel_diagnostics?.tv.attention_states?.length
                              ? aiModeData.channel_diagnostics.tv.attention_states.join(', ')
                              : '-'}
                          </p>
                        </div>
                        <div className="rounded-xl border border-slate-200 bg-white p-4">
                          <p className="text-xs font-semibold uppercase tracking-wide text-primary">Digital Effectiveness</p>
                          <p className="mt-2 text-xs font-semibold uppercase tracking-wide text-slate-500">Working States</p>
                          <p className="mt-1 text-sm text-slate-700">
                            {aiModeData.channel_diagnostics?.digital.working_states?.length
                              ? aiModeData.channel_diagnostics.digital.working_states.join(', ')
                              : '-'}
                          </p>
                          <p className="mt-3 text-xs font-semibold uppercase tracking-wide text-slate-500">Needs Attention</p>
                          <p className="mt-1 text-sm text-slate-700">
                            {aiModeData.channel_diagnostics?.digital.attention_states?.length
                              ? aiModeData.channel_diagnostics.digital.attention_states.join(', ')
                              : '-'}
                          </p>
                        </div>
                      </div>

                      <div className="grid gap-3 xl:grid-cols-2">
                        {renderSummaryActionList('Where To Increase', 'positive', summaryJson?.increase_markets ?? [])}
                        {renderSummaryActionList('Where To Protect / Rebalance', 'risk', summaryJson?.decrease_markets ?? [])}
                      </div>

                    </>
                  ) : (
                    <div className="rounded-xl border border-slate-200 bg-white p-4">
                      <p className="text-xs font-semibold uppercase tracking-wide text-primary">Trinity Narrative</p>
                      <pre className="mt-3 whitespace-pre-wrap font-sans text-sm leading-relaxed text-slate-700">{aiModeData.ai_brief}</pre>
                    </div>
                  )}

                  <div className="rounded-xl border border-slate-200 bg-white p-4">
                    <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">State Signal Table</p>
                    <div className="mt-2 overflow-x-auto rounded-lg border border-slate-200">
                      <table className="min-w-full divide-y divide-slate-200 text-sm">
                        <thead className="bg-slate-50 text-slate-600">
                          <tr>
                            <th className="px-3 py-2 text-left">State</th>
                            <th className="px-3 py-2 text-right">YoY %</th>
                            <th className="px-3 py-2 text-right">Salience %</th>
                            <th className="px-3 py-2 text-right">Brand Share %</th>
                            <th className="px-3 py-2 text-left">Leader Position</th>
                            <th className="px-3 py-2 text-right">TV Eff %</th>
                            <th className="px-3 py-2 text-right">Digital Eff %</th>
                            <th className="px-3 py-2 text-right">Responsiveness %</th>
                            <th className="px-3 py-2 text-left">Quadrant</th>
                            <th className="px-3 py-2 text-left">Action</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-100 bg-white text-slate-700">
                          {aiModeData.market_cards.map((row) => (
                            <tr key={`ai-state-row-${row.market}`}>
                              <td className="px-3 py-2.5 font-semibold text-dark-text">{row.market}</td>
                              <td className={`px-3 py-2.5 text-right font-semibold ${row.yoy_growth_pct >= 0 ? 'text-success' : 'text-danger'}`}>
                                {formatSignedPct(row.yoy_growth_pct)}
                              </td>
                              <td className="px-3 py-2.5 text-right">{formatPct(row.category_salience_pct)}</td>
                              <td className="px-3 py-2.5 text-right">{formatPct(row.brand_market_share_pct)}</td>
                              <td className="px-3 py-2.5 text-xs">{row.leader_position ?? '-'}</td>
                              <td className="px-3 py-2.5 text-right">{formatPct(row.tv_effectiveness_pct)}</td>
                              <td className="px-3 py-2.5 text-right">{formatPct(row.digital_effectiveness_pct)}</td>
                              <td className="px-3 py-2.5 text-right">{formatPct(row.media_responsiveness_pct)}</td>
                              <td className="px-3 py-2.5 text-xs">{row.investment_quadrant?.replaceAll('_', ' ') ?? '-'}</td>
                              <td className="px-3 py-2.5 text-xs text-slate-700">{row.recommendation_action}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>

                  {userFacingNotes.length > 0 ? (
                    <div className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
                      {userFacingNotes.join(' ')}
                    </div>
                  ) : null}
                </div>
              ) : null}
            </section>
          </div>
        </div>
      </div>
    )
  }

  function renderStep1SplitPieCard(mode: 'baseline' | 'optimized') {
    if (!brandAllocation || step1SplitRows.length === 0) return null
    const title = mode === 'baseline' ? 'Previous Brand Split' : 'Optimized Brand Split'
    const totalBudget =
      mode === 'baseline'
        ? Number(brandAllocation.summary.baseline_total_budget ?? 0)
        : Number(brandAllocation.summary.target_total_budget ?? 0)
    const pieces = step1SplitRows.map((row) => ({
      brand: row.brand,
      share: mode === 'baseline' ? row.baselineShare : row.optimizedShare,
      budget: mode === 'baseline' ? row.baselineBudget : row.allocatedBudget,
    }))
    let cursor = 0
    const stops: string[] = []
    for (const piece of pieces) {
      const pieceColor = getShareGreenColor(piece.share)
      const next = Math.min(100, cursor + Math.max(0, piece.share))
      stops.push(`${pieceColor} ${cursor.toFixed(3)}% ${next.toFixed(3)}%`)
      cursor = next
    }
    if (cursor < 100) {
      stops.push(`#E2E8F0 ${cursor.toFixed(3)}% 100%`)
    }
    const pieBackground = `conic-gradient(${stops.join(', ')})`

    return (
      <div className="rounded-xl border border-slate-200 bg-white p-4">
        <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">{title}</p>
        <div className="mt-3 grid gap-4 lg:grid-cols-[220px_1fr]">
          <div className="flex items-center justify-center">
            <div className="relative h-52 w-52 rounded-full border border-slate-200" style={{ background: pieBackground }}>
              <div className="absolute inset-[28%] flex items-center justify-center rounded-full border border-slate-200 bg-white text-center">
                <div>
                  <p className="text-[10px] font-semibold uppercase tracking-wide text-slate-500">Total</p>
                  <p className="text-sm font-bold text-dark-text">{formatCurrencyBn(totalBudget)}</p>
                </div>
              </div>
            </div>
          </div>
          <div className="max-h-56 space-y-2 overflow-y-auto pr-1">
            {pieces.map((piece) => {
              const pieceColor = getShareGreenColor(piece.share)
              return (
              <div key={`${mode}-${piece.brand}`} className="flex items-center justify-between rounded-lg border border-slate-200 bg-slate-50 px-3 py-2">
                <div className="flex items-center gap-2">
                  <span className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: pieceColor }} />
                  <span className="text-sm font-semibold text-dark-text">{piece.brand}</span>
                </div>
                <div className="text-right">
                  <p className="text-sm font-semibold text-dark-text">{formatPct(piece.share)}</p>
                  <p className="text-xs text-slate-500">{formatCurrencyMn(piece.budget)}</p>
                </div>
              </div>
            )})}
          </div>
        </div>
      </div>
    )
  }

  function renderScenarioMarketModal() {
    if (!scenarioMarketModal) return null
    const { row, tone } = scenarioMarketModal
    const toneChipClass = tone === 'increase' ? 'bg-emerald-50 text-emerald-700' : 'bg-rose-50 text-rose-700'
    const closeModal = () => setScenarioMarketModal(null)
    const deltaClass = (value: number) => (value >= 0 ? 'text-success' : 'text-danger')

    return (
      <div className="fixed inset-0 z-50">
        <button
          type="button"
          aria-label="Close State Detail"
          className="absolute inset-0 bg-slate-900/45"
          onClick={closeModal}
        />
        <div className="absolute inset-0 flex items-center justify-center p-3 sm:p-6">
          <div className="w-full max-w-3xl overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-2xl">
            <div className="flex items-center justify-between gap-3 border-b border-slate-200 bg-white px-5 py-3">
              <div>
                <p className="text-xs font-semibold uppercase tracking-wide text-primary">State Detail</p>
                <p className="text-base font-semibold text-dark-text">{row.market}</p>
              </div>
              <div className="flex items-center gap-2">
                <span className={`rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide ${toneChipClass}`}>
                  {tone === 'increase' ? 'Budget Increased' : 'Budget Decreased'}
                </span>
                <button
                  type="button"
                  onClick={closeModal}
                  className="rounded-lg border border-slate-300 bg-white p-1.5 text-slate-600 hover:bg-slate-100"
                >
                  <X className="h-4 w-4" />
                </button>
              </div>
            </div>

            <div className="space-y-3 p-5">
              <div className="grid gap-3 sm:grid-cols-2">
                <div className="rounded-xl border border-slate-200 bg-slate-50 p-3">
                  <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Budget Share</p>
                  <p className="mt-1 text-sm text-slate-700">
                    {formatPct(row.old_budget_share_pct, 2)} {'->'} {formatPct(row.new_budget_share_pct, 2)}
                  </p>
                  <p className={`mt-1 text-sm font-semibold ${deltaClass(row.budget_share_change_pct)}`}>
                    {formatSignedPct(row.budget_share_change_pct, 2)}
                  </p>
                </div>
                <div className="rounded-xl border border-slate-200 bg-slate-50 p-3">
                  <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Spend Shift</p>
                  <p className={`mt-2 text-lg font-bold ${deltaClass(row.spend_delta_mn)}`}>
                    {formatSignedCurrencyMn(row.spend_delta_mn)}
                  </p>
                </div>
              </div>

              <div className="grid gap-3 sm:grid-cols-2">
                <div className="rounded-xl border border-slate-200 bg-white p-3">
                  <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">TV Split</p>
                  <p className="mt-1 text-sm text-slate-700">
                    {formatPct(row.old_tv_split_pct, 2)} {'->'} {formatPct(row.new_tv_split_pct, 2)}
                  </p>
                  <p className={`mt-1 text-sm font-semibold ${deltaClass(row.tv_split_change_pct)}`}>
                    {formatSignedPct(row.tv_split_change_pct, 2)}
                  </p>
                </div>
                <div className="rounded-xl border border-slate-200 bg-white p-3">
                  <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Digital Split</p>
                  <p className="mt-1 text-sm text-slate-700">
                    {formatPct(row.old_digital_split_pct, 2)} {'->'} {formatPct(row.new_digital_split_pct, 2)}
                  </p>
                  <p className={`mt-1 text-sm font-semibold ${deltaClass(row.digital_split_change_pct)}`}>
                    {formatSignedPct(row.digital_split_change_pct, 2)}
                  </p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="h-screen bg-slate-100 text-dark-text">
      <header className="h-16 border-b border-slate-200 bg-white shadow-sm">
        <div className="flex h-full items-center justify-between px-4 sm:px-6 lg:px-8">
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary text-white">
              <BarChart3 className="h-5 w-5" />
            </div>
            <div>
              <p className="text-xs uppercase tracking-wide text-neutral">Planning Suite</p>
              <h1 className="text-xl font-bold text-dark-text">Marketing Budget Allocation</h1>
            </div>
          </div>

          <div className="hidden rounded-full border border-slate-200 bg-slate-50 px-3 py-1.5 sm:block">
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Portfolio Optimization Workspace</p>
          </div>
        </div>
      </header>

      <div className="flex h-[calc(100vh-64px)] overflow-hidden">
        <aside className="hidden w-64 flex-shrink-0 border-r border-slate-200 bg-white px-4 py-6 lg:block">
          <button
            type="button"
            onClick={() => setActiveMainTab('s_curves')}
            className={`flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-semibold ${
              activeMainTab === 's_curves'
                ? 'border border-primary/30 bg-primary/10 text-primary'
                : 'border border-slate-200 bg-white text-slate-700'
            }`}
          >
            <BarChart3 className="h-4 w-4" />
            Insights
          </button>
          <button
            type="button"
            onClick={() => setActiveMainTab('budget_allocation')}
            className={`mt-2 flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-semibold ${
              activeMainTab === 'budget_allocation'
                ? 'border border-primary/30 bg-primary/10 text-primary'
                : 'border border-slate-200 bg-white text-slate-700'
            }`}
          >
            <Target className="h-4 w-4" />
            Budget Allocation
          </button>
        </aside>

        <main className="flex-1 overflow-y-auto p-4 sm:p-5 lg:p-6">
          {activeMainTab === 's_curves' ? (
            <div className="w-full space-y-5">
              {renderSCurvesSection()}
              <section className="rounded-xl border border-slate-200 bg-white p-4 shadow-panel">
                <p className="text-sm text-slate-600">Use these response curves as pre-read, then continue to budget optimization.</p>
                <button
                  type="button"
                  onClick={() => setActiveMainTab('budget_allocation')}
                  className="mt-3 rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700"
                >
                  Go To Budget Allocation
                </button>
              </section>
            </div>
          ) : (
            <div className="w-full space-y-5">
            <section className="rounded-xl border border-slate-200 bg-white p-4 shadow-panel">
              <div className="mb-2 flex items-start justify-between gap-3">
                <div>
                  <p className="text-xs font-semibold uppercase tracking-wide text-primary">Step 1</p>
                  <h2 className="mt-1 text-lg font-semibold text-dark-text">National To Brand Budget Allocation</h2>
                </div>
                {step2Enabled ? (
                  <button
                    type="button"
                    onClick={() => setStep1Collapsed((prev) => !prev)}
                    className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-xs font-semibold text-slate-700 hover:bg-slate-50"
                  >
                    {step1Collapsed ? 'Expand Step 1' : 'Collapse Step 1'}
                  </button>
                ) : null}
              </div>
              {step1Collapsed ? (
                <div className="mt-2 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm">
                  <p className="text-slate-700">
                    Optimized Budget: <span className="font-semibold">{formatCurrencyBn(brandAllocation?.summary.target_total_budget)}</span>
                  </p>
                  <p className="text-slate-700">
                    Estimated Revenue Increase:{' '}
                    <span
                      className={`font-semibold ${
                        (brandAllocation?.summary.estimated_total_revenue_uplift_pct ?? 0) >= 0 ? 'text-success' : 'text-danger'
                      }`}
                    >
                      {formatSignedPct(brandAllocation?.summary.estimated_total_revenue_uplift_pct)}
                    </span>
                  </p>
                </div>
              ) : (
                <>
                  {renderStep1Controls('step1')}

                  {brandAllocationLoading ? (
                    <p className="mt-4 text-sm text-slate-500">Calculating national allocation...</p>
                  ) : null}

                  {step1Error ? (
                    <div className="mt-3 rounded-lg border border-danger/20 bg-danger/10 px-3 py-2 text-sm text-danger">
                      {step1Error}
                    </div>
                  ) : null}

                  {!brandAllocationLoading && !brandAllocation && !step1Error ? (
                    <div className="mt-3 rounded-lg border border-dashed border-slate-300 bg-slate-50 px-3 py-3 text-sm text-slate-600">
                      Initial Budget: <span className="font-semibold">{formatCurrencyBn(step1BaselineBudget)}</span>. Configure Step 1 inputs and click{' '}
                      <span className="font-semibold">Run Step 1</span> to generate national-to-brand allocation.
                    </div>
                  ) : null}

                  {brandAllocation ? (
                    <div className="mt-3 space-y-3">
                      <div className={`grid gap-3 ${showIncrementalBudget ? 'md:grid-cols-2' : 'md:grid-cols-1'}`}>
                        <div className="rounded-xl border border-slate-200 bg-white p-3">
                          <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Optimized Total Budget (INR Mn/Bn)</p>
                          <p className="mt-1 text-xl font-bold text-dark-text">{formatCurrencyBn(brandAllocation.summary.target_total_budget)}</p>
                        </div>
                        {showIncrementalBudget ? (
                          <div className="rounded-xl border border-slate-200 bg-white p-3">
                            <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Incremental Budget (INR Mn/Bn)</p>
                            <p
                              className={`mt-1 text-xl font-bold ${
                                brandAllocation.summary.incremental_budget > 0
                                  ? 'text-success'
                                  : brandAllocation.summary.incremental_budget < 0
                                    ? 'text-danger'
                                    : 'text-dark-text'
                              }`}
                            >
                              {formatSignedCurrencyBn(brandAllocation.summary.incremental_budget)}
                            </p>
                          </div>
                        ) : null}
                      </div>

                      <div className="rounded-xl border border-slate-200 bg-slate-50 p-3">
                        <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Result Metric: Estimated Revenue Increase</p>
                        <div className="mt-1 flex flex-wrap items-center gap-4">
                          <p
                            className={`text-lg font-bold ${
                              (brandAllocation.summary.estimated_total_revenue_uplift_abs ?? 0) > 0
                                ? 'text-success'
                                : (brandAllocation.summary.estimated_total_revenue_uplift_abs ?? 0) < 0
                                  ? 'text-danger'
                                  : 'text-dark-text'
                            }`}
                          >
                            {formatSignedCurrencyBn(brandAllocation.summary.estimated_total_revenue_uplift_abs)}
                          </p>
                          <p
                            className={`text-sm font-semibold ${
                              (brandAllocation.summary.estimated_total_revenue_uplift_pct ?? 0) > 0
                                ? 'text-success'
                                : (brandAllocation.summary.estimated_total_revenue_uplift_pct ?? 0) < 0
                                  ? 'text-danger'
                                  : 'text-slate-700'
                            }`}
                          >
                            {formatSignedPct(brandAllocation.summary.estimated_total_revenue_uplift_pct)}
                          </p>
                        </div>
                      </div>

                      <div className="space-y-2">
                        <div className="flex flex-wrap items-center justify-between gap-2">
                          <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                            Brand Split Before And After Optimization
                          </p>
                          <div className="flex items-center gap-2">
                            {!step1EditMode ? (
                              <button
                                type="button"
                                onClick={handleEditStep1Allocations}
                                className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-xs font-semibold text-slate-700 hover:bg-slate-50"
                              >
                                Edit Allocated Budget
                              </button>
                            ) : (
                              <>
                                <button
                                  type="button"
                                  onClick={resetStep1AllocationDraft}
                                  className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-xs font-semibold text-slate-700 hover:bg-slate-50"
                                >
                                  Reset Draft
                                </button>
                                <button
                                  type="button"
                                  onClick={handleCancelStep1Allocations}
                                  className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-xs font-semibold text-slate-700 hover:bg-slate-50"
                                >
                                  Cancel
                                </button>
                                <button
                                  type="button"
                                  onClick={handleSaveStep1Allocations}
                                  className="rounded-lg bg-primary px-3 py-1.5 text-xs font-semibold text-white hover:bg-blue-700"
                                >
                                  Save Allocation
                                </button>
                              </>
                            )}
                          </div>
                        </div>

                        {step1EditMode ? (
                          <>
                            <div className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-600">
                              Edited Total Budget: <span className="font-semibold text-dark-text">{formatCurrencyBn(step1EditedTotalBudget)}</span>
                            </div>

                            {step1EditError ? (
                              <div className="rounded-lg border border-danger/20 bg-danger/10 px-3 py-2 text-sm text-danger">
                                {step1EditError}
                              </div>
                            ) : null}

                            <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white">
                              <table className="min-w-full text-sm">
                                <thead className="bg-slate-50">
                                  <tr className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                                    <th className="px-4 py-2 text-left">Brand</th>
                                    <th className="px-4 py-2 text-right">Initial Budget (INR Bn)</th>
                                    <th className="px-4 py-2 text-right">Initial Split (%)</th>
                                    <th className="px-4 py-2 text-right">Min-Max (INR Bn)</th>
                                    <th className="px-4 py-2 text-right">Allocated (INR Bn)</th>
                                    <th className="px-4 py-2 text-right">Optimized Split (%)</th>
                                  </tr>
                                </thead>
                                <tbody className="divide-y divide-slate-200">
                                  {brandAllocation.allocation_rows.map((row, index) => {
                                    const baselineSplit =
                                      Math.abs(brandAllocation.summary.baseline_total_budget) > 1e-9
                                        ? (row.baseline_budget / brandAllocation.summary.baseline_total_budget) * 100
                                        : 0
                                    const draftBn = Number(step1AllocationDraft[row.brand])
                                    const allocatedValue =
                                      step1EditMode && Number.isFinite(draftBn) ? draftBn * 1_000_000_000 : row.allocated_budget
                                    const minAllowed = Number(row.min_allowed_budget ?? row.baseline_budget * 0.75)
                                    const maxAllowed = Number(row.max_allowed_budget ?? row.baseline_budget * 1.25)
                                    const optimizedSplit =
                                      Math.abs(brandAllocation.summary.target_total_budget) > 1e-9
                                        ? (allocatedValue / brandAllocation.summary.target_total_budget) * 100
                                        : 0
                                    return (
                                      <tr key={row.brand} className={index % 2 === 0 ? 'bg-white' : 'bg-slate-50/50'}>
                                        <td className="px-4 py-2.5 font-semibold text-dark-text">{row.brand}</td>
                                        <td className="px-4 py-2.5 text-right text-slate-700">{formatCurrencyBn(row.baseline_budget)}</td>
                                        <td className="px-4 py-2.5 text-right text-slate-700">{formatPct(baselineSplit)}</td>
                                        <td className="px-4 py-2.5 text-right text-slate-700">
                                          {formatCurrencyBn(minAllowed)} - {formatCurrencyBn(maxAllowed)}
                                        </td>
                                        <td className="px-4 py-2.5 text-right text-slate-700">
                                          <input
                                            type="number"
                                            min={String(minAllowed / 1_000_000_000)}
                                            max={String(maxAllowed / 1_000_000_000)}
                                            step="0.0001"
                                            value={step1AllocationDraft[row.brand] ?? ''}
                                            onChange={(event) => handleStep1DraftChange(row.brand, event.target.value)}
                                            className="ml-auto w-36 rounded-lg border border-slate-300 bg-white px-2 py-1.5 text-right text-sm text-slate-700 focus:border-[#2563EB] focus:outline-none focus:ring-2 focus:ring-blue-200"
                                            title={`Allowed range: ${formatCurrencyBn(minAllowed)} to ${formatCurrencyBn(maxAllowed)}`}
                                          />
                                        </td>
                                        <td className="px-4 py-2.5 text-right text-slate-700">{formatPct(optimizedSplit)}</td>
                                      </tr>
                                    )
                                  })}
                                </tbody>
                              </table>
                            </div>
                          </>
                        ) : (
                          <div className="grid gap-3 xl:grid-cols-2">
                            {renderStep1SplitPieCard('baseline')}
                            {renderStep1SplitPieCard('optimized')}
                          </div>
                        )}
                      </div>

                      {!step2Enabled ? (
                        <div className="flex justify-end">
                          <button
                            type="button"
                            onClick={() => {
                              setStep2Enabled(true)
                              setStep2SetupCollapsed(false)
                              setStep1Collapsed(true)
                            }}
                            disabled={step1EditMode}
                            className="rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:bg-slate-400"
                          >
                            Go To Brand-Market Allocation
                          </button>
                        </div>
                      ) : null}
                    </div>
                  ) : null}
                </>
              )}
            </section>

            {step2Enabled ? (
              <>
                <section className="rounded-xl border border-slate-200 bg-white p-4 shadow-panel sm:p-5">
                  <div className="mb-3 flex items-center justify-between gap-3">
                    <div>
                      <h2 className="text-lg font-semibold text-dark-text">Step 2: Brand And Market Scenario Generation</h2>
                      <p className="mt-1 text-sm text-slate-500">
                        {step2SetupCollapsed
                          ? 'Setup collapsed after generate. Scenario selection stays active below.'
                          : 'Follow the flow: select brand, provide AI intent, edit constraints, then generate scenarios.'}
                      </p>
                    </div>
                    <button
                      type="button"
                      onClick={() => setStep2SetupCollapsed((prev) => !prev)}
                      className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-50"
                    >
                      {step2SetupCollapsed ? 'Open Setup' : 'Collapse Setup'}
                    </button>
                  </div>
                  {step2SetupCollapsed ? (
                    <button
                      type="button"
                      onClick={() => setStep2SetupCollapsed(false)}
                      className="mb-2 w-full rounded-lg border border-blue-200 bg-blue-50 px-3 py-2 text-left text-xs font-semibold text-primary hover:bg-blue-100"
                    >
                      Step 2 Setup is collapsed. Click to reopen inputs and constraints.
                    </button>
                  ) : null}
                  <div
                    className={`overflow-hidden transition-all duration-300 ease-out ${
                      step2SetupCollapsed ? 'max-h-0 -translate-y-1 opacity-0 pointer-events-none' : 'max-h-[2600px] translate-y-0 opacity-100'
                    }`}
                  >
                    <div className="pt-1">{renderSetupForm('step2')}</div>
                  </div>
                </section>
              </>
            ) : (
              <section className="rounded-xl border border-dashed border-slate-300 bg-white p-4 shadow-panel">
                <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Step 2 Locked</p>
                <p className="mt-1 text-sm text-slate-600">Complete Step 1 and click "Go To Brand-Market Allocation" to continue.</p>
              </section>
            )}
            {step2Enabled ? (
              scenarioResults ? (
                <section className="space-y-5 rounded-xl border border-slate-200 bg-white p-5 shadow-panel sm:p-6">
                  <div className="flex items-center gap-2 text-sm font-semibold text-success">
                    <CheckCircle2 className="h-4 w-4" />
                    Scenario generation completed.
                  </div>
                  {scenarioResults.generation_notes.length > 0 ? (
                    <div className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
                      {scenarioResults.generation_notes.join(' ')}
                    </div>
                  ) : null}
                  <div className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2">
                    <p className="text-sm font-semibold text-dark-text">{scenarioResults.summary.scenario_count} scenarios generated!</p>
                    <p className="mt-1 text-xs text-slate-600">
                      Highest Revenue: {formatSignedPct(scenarioResults.anchors.best_revenue?.revenue_uplift_pct)}
                    </p>
                    <p className="mt-1 text-xs text-slate-600">
                      Budget Utilized (Top shown): {scenarioResults.items.length > 0 ? formatCurrencyBn(scenarioResults.items[0].total_new_spend) : '-'}
                    </p>
                    <p className="mt-1 text-xs text-slate-600">
                      Max Budget Utilized (Page): {scenarioMaxBudgetUtilizedPct.toFixed(1)}%
                    </p>
                  </div>

                  <div className="rounded-xl border border-slate-200 bg-white p-4">
                    <div className="grid gap-2 sm:grid-cols-2">
                      <select value={scenarioSortKey} onChange={(event) => { setScenarioSortKey(event.target.value); setScenarioPage(1) }} className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-700 focus:border-[#2563EB] focus:outline-none focus:ring-2 focus:ring-blue-200">
                        <option value="revenue_uplift_pct">Sort by: Revenue</option>
                      </select>
                      <select value={scenarioSortDir} onChange={(event) => { setScenarioSortDir(event.target.value === 'asc' ? 'asc' : 'desc'); setScenarioPage(1) }} className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-700 focus:border-[#2563EB] focus:outline-none focus:ring-2 focus:ring-blue-200">
                        <option value="desc">Descending</option>
                        <option value="asc">Ascending</option>
                      </select>
                    </div>

                    <div className="mt-3 flex items-center justify-between rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-600">
                      <p>
                        {scenarioResults.pagination.total_count > 0
                          ? `Showing ${scenarioPageRange.start}-${scenarioPageRange.end} of ${scenarioResults.pagination.total_count}`
                          : 'Showing 0 of 0'}
                      </p>
                      <div className="flex items-center gap-2">
                        <button type="button" onClick={() => setScenarioPage((prev) => Math.max(1, prev - 1))} disabled={scenarioResults.pagination.page <= 1} className="rounded border border-slate-300 bg-white px-2 py-1 font-semibold text-slate-700 disabled:cursor-not-allowed disabled:opacity-60">Previous</button>
                        <span>Page {Math.max(1, scenarioResults.pagination.page)} / {Math.max(1, scenarioResults.pagination.total_pages)}</span>
                        <button type="button" onClick={() => setScenarioPage((prev) => Math.min(Math.max(1, scenarioResults.pagination.total_pages), prev + 1))} disabled={scenarioResults.pagination.page >= Math.max(1, scenarioResults.pagination.total_pages)} className="rounded border border-slate-300 bg-white px-2 py-1 font-semibold text-slate-700 disabled:cursor-not-allowed disabled:opacity-60">Next</button>
                      </div>
                    </div>

                    <div className="mt-3 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-700">
                      {selectedScenario ? (
                        <>
                          <span className="font-semibold text-dark-text">{selectedScenario.scenario_id}</span>
                          <span className="mx-2 text-slate-400">|</span>
                          Revenue: <span className={`font-semibold ${selectedScenario.revenue_uplift_pct >= 0 ? 'text-success' : 'text-danger'}`}>{formatSignedPct(selectedScenario.revenue_uplift_pct, 2)}</span>
                          <span className="mx-2 text-slate-400">|</span>
                          Budget Utilized: <span className="font-semibold text-dark-text">{formatCurrencyBn(selectedScenario.total_new_spend)}</span>
                        </>
                      ) : (
                        <>
                          <span className="text-slate-500">No scenario selected.</span>
                          {scenarioResults.items.length > 0 ? (
                            <>
                              <span className="mx-2 text-slate-400">|</span>
                              Top shown: <span className="font-semibold text-dark-text">{scenarioResults.items[0].scenario_id}</span>
                              <span className="mx-2 text-slate-400">|</span>
                              Budget Utilized: <span className="font-semibold text-dark-text">{formatCurrencyBn(scenarioResults.items[0].total_new_spend)}</span>
                            </>
                          ) : null}
                        </>
                      )}
                    </div>

                    {scenarioResults.pagination.total_count === 0 ? (
                      <div className="mt-3 rounded-lg border border-slate-200 bg-slate-50 px-3 py-8 text-center text-sm font-semibold text-slate-600">
                        No scenarios match current filters.
                      </div>
                    ) : (
                      <>
                        <div className="mt-3 rounded-lg border border-slate-200 bg-white px-2 py-2 sm:px-3">
                          <svg className="w-full" viewBox={`0 0 ${scenarioChartWidth} 320`} role="img" aria-label="Revenue and budget utilized comparison chart">
                            {(() => {
                              const chartHeight = 320
                              const left = 66
                              const right = 66
                              const top = 32
                              const bottom = 46
                              const plotWidth = scenarioChartWidth - left - right
                              const plotHeight = chartHeight - top - bottom
                              const revenues = scenarioResults.items.map((item) => Number(item.revenue_uplift_pct ?? 0))
                              const revMinRaw = Math.min(0, ...revenues)
                              const revMaxRaw = Math.max(1, ...revenues)
                              const revAxisMin = revMinRaw < -0.001 ? revMinRaw * 1.12 : 0
                              const revAxisMax = revMaxRaw * 1.12
                              const budgetMax = Math.max(100, scenarioBudgetAxisMax)
                              const targetBudget = Number(scenarioResults.summary.target_budget ?? 0)
                              const revSpan = Math.max(1e-6, revAxisMax - revAxisMin)
                              const yRev = (value: number) => top + ((revAxisMax - value) / revSpan) * plotHeight
                              const zeroRevY = yRev(0)
                              const yBudget = (value: number) => {
                                const clamped = Math.max(0, Math.min(budgetMax, value))
                                const upRange = Math.max(1, zeroRevY - top)
                                return zeroRevY - (clamped / budgetMax) * upRange
                              }
                              const revTicks =
                                revAxisMin < -0.001
                                  ? [revAxisMin, revAxisMin * 0.5, 0, revAxisMax * 0.5, revAxisMax]
                                  : [0, revAxisMax * 0.25, revAxisMax * 0.5, revAxisMax * 0.75, revAxisMax]
                              const budgetTicks = [0, budgetMax * 0.25, budgetMax * 0.5, budgetMax * 0.75, budgetMax]
                              const maxBudgetLineY = yBudget(scenarioMaxBudgetUtilizedPct)
                              return (
                                <>
                                  {revTicks.map((tick, idx) => {
                                    const y = yRev(tick)
                                    return (
                                      <g key={`rev-tick-${idx}`}>
                                        <line x1={left} x2={scenarioChartWidth - right} y1={y} y2={y} stroke={tick === 0 ? '#94A3B8' : '#E2E8F0'} />
                                        <text x={left - 8} y={y + 4} textAnchor="end" fill="#64748B" fontSize="10">
                                          {tick.toFixed(1)}%
                                        </text>
                                      </g>
                                    )
                                  })}
                                  {budgetTicks.map((tick, idx) => {
                                    const y = yBudget(tick)
                                    return (
                                      <text key={`budget-axis-${idx}`} x={scenarioChartWidth - right + 8} y={y + 4} textAnchor="start" fill="#64748B" fontSize="10">
                                        {tick.toFixed(0)}%
                                      </text>
                                    )
                                  })}
                                  <line
                                    x1={left}
                                    x2={scenarioChartWidth - right}
                                    y1={maxBudgetLineY}
                                    y2={maxBudgetLineY}
                                    stroke="#3B82F6"
                                    strokeDasharray="4 4"
                                  />
                                  {scenarioResults.items.map((item, idx) => {
                                    const groupWidth = plotWidth / Math.max(1, scenarioResults.items.length)
                                    const centerX = left + groupWidth * (idx + 0.5)
                                    const barWidth = Math.min(14, Math.max(9, groupWidth * 0.11))
                                    const gap = Math.max(22, Math.min(34, groupWidth * 0.34))
                                    const revX = centerX - barWidth - gap / 2
                                    const budgetX = centerX + gap / 2
                                    const revYv = yRev(item.revenue_uplift_pct)
                                    const revH = Math.abs(zeroRevY - revYv)
                                    const utilPct = targetBudget > 1e-12 ? (Number(item.total_new_spend ?? 0) / targetBudget) * 100 : 0
                                    const budY = yBudget(utilPct)
                                    const budH = Math.max(1, zeroRevY - budY)
                                    const revLabelX = revX + barWidth / 2 - 4
                                    const budgetLabelX = budgetX + barWidth / 2 + 4
                                    const labelYMin = top + 12
                                    const labelYMax = chartHeight - bottom - 6
                                    let finalRevLabelY = Math.max(
                                      labelYMin,
                                      Math.min(labelYMax, Math.min(revYv, zeroRevY) - 6),
                                    )
                                    let finalBudgetLabelY = Math.max(labelYMin, Math.min(labelYMax, budY - 6))
                                    if (Math.abs(finalRevLabelY - finalBudgetLabelY) < 10) {
                                      finalBudgetLabelY = Math.min(labelYMax, finalBudgetLabelY + 10)
                                    }
                                    const isSelected = selectedScenarioId === item.scenario_id
                                    const label = item.scenario_id.length > 14 ? `${item.scenario_id.slice(0, 14)}...` : item.scenario_id
                                    return (
                                      <g key={item.scenario_id} onClick={() => setSelectedScenarioId(item.scenario_id)} style={{ cursor: 'pointer' }}>
                                        {isSelected ? (
                                          <rect x={centerX - groupWidth / 2 + 8} y={top} width={groupWidth - 16} height={plotHeight} fill="#EFF6FF" stroke="#93C5FD" rx={6} />
                                        ) : null}
                                        <rect x={revX} y={Math.min(revYv, zeroRevY)} width={barWidth} height={Math.max(1, revH)} fill="#22C55E" />
                                        <rect x={budgetX} y={budY} width={barWidth} height={budH} fill="#2563EB" />
                                        <text x={revLabelX} y={finalRevLabelY} textAnchor="end" fontSize="10" fill="#0F172A" fontWeight="800">
                                          {formatSignedPct(item.revenue_uplift_pct, 1)}
                                        </text>
                                        <text
                                          x={budgetLabelX}
                                          y={finalBudgetLabelY}
                                          textAnchor="start"
                                          fontSize="10"
                                          fill="#0F172A"
                                          fontWeight="800"
                                        >
                                          {utilPct.toFixed(1)}%
                                        </text>
                                        <text x={centerX} y={chartHeight - 18} textAnchor="middle" fontSize="11" fill="#334155" fontWeight={isSelected ? '700' : '500'}>
                                          {label}
                                        </text>
                                      </g>
                                    )
                                  })}
                                  <line x1={left} x2={left} y1={top} y2={chartHeight - bottom} stroke="#94A3B8" />
                                  <line x1={scenarioChartWidth - right} x2={scenarioChartWidth - right} y1={top} y2={chartHeight - bottom} stroke="#94A3B8" />
                                  <line x1={left} x2={scenarioChartWidth - right} y1={chartHeight - bottom} y2={chartHeight - bottom} stroke="#94A3B8" />
                                </>
                              )
                            })()}
                          </svg>
                          <div className="mt-2 flex items-center justify-center gap-4 text-xs text-slate-600">
                            <span className="inline-flex items-center gap-1"><span className="h-2.5 w-2.5 rounded-sm bg-green-500" />Revenue %</span>
                            <span className="inline-flex items-center gap-1"><span className="h-2.5 w-2.5 rounded-sm bg-primary" />Budget Utilized %</span>
                          </div>
                        </div>
                      </>
                    )}

                    <div className="mt-4 rounded-lg border border-slate-200 bg-slate-50 p-3">
                      <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">FILTER SCENARIOS</p>
                      <div className="mt-2 grid gap-2 sm:grid-cols-2">
                        <div>
                          <label className="text-xs font-semibold uppercase tracking-wide text-slate-500" htmlFor="scenario-min-revenue">
                            Min Revenue % Increase
                          </label>
                          <input
                            id="scenario-min-revenue"
                            type="number"
                            step="0.01"
                            value={scenarioMinRevenuePct}
                            onChange={(event) => {
                              setScenarioMinRevenuePct(event.target.value)
                              setScenarioPage(1)
                            }}
                            className="mt-1 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-700 focus:border-[#2563EB] focus:outline-none focus:ring-2 focus:ring-blue-200"
                            placeholder="e.g. 2.5"
                          />
                        </div>
                        <div>
                          <label className="text-xs font-semibold uppercase tracking-wide text-slate-500" htmlFor="scenario-max-budget-utilized">
                            Max Budget Utilized %
                          </label>
                          <input
                            id="scenario-max-budget-utilized"
                            type="number"
                            step="0.01"
                            value={scenarioMaxBudgetUtilizedPctFilter}
                            onChange={(event) => {
                              setScenarioMaxBudgetUtilizedPctFilter(event.target.value)
                              setScenarioPage(1)
                            }}
                            className="mt-1 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-700 focus:border-[#2563EB] focus:outline-none focus:ring-2 focus:ring-blue-200"
                            placeholder="e.g. 100"
                          />
                        </div>
                      </div>
                    </div>

                    {selectedScenario ? (
                      <div className="mt-4">
                        <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Selected Scenario Market Split</p>
                        <div className="mt-2 flex flex-wrap items-center justify-between gap-2 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2">
                          <p className="text-xs font-semibold text-slate-700">
                            Shift View: {selectedScenarioBudgetFlow.increased.length} increase markets | {selectedScenarioBudgetFlow.decreased.length} decrease markets
                          </p>
                          <select
                            value={scenarioFlowSortKey}
                            onChange={(event) => setScenarioFlowSortKey(event.target.value === 'spend' ? 'spend' : 'share')}
                            className="rounded-lg border border-slate-300 bg-white px-2.5 py-1.5 text-xs font-semibold text-slate-700 focus:border-[#2563EB] focus:outline-none focus:ring-2 focus:ring-blue-200"
                          >
                            <option value="share">Sort by Share Shift (pp)</option>
                            <option value="spend">Sort by Spend Shift (INR Mn)</option>
                          </select>
                        </div>

                        <div className="mt-3 grid gap-3 lg:grid-cols-2">
                          <div className="rounded-xl border border-emerald-200 bg-emerald-50/40 p-3">
                            <p className="text-xs font-semibold uppercase tracking-wide text-emerald-700">Where Budget Increased</p>
                            <div className="mt-2 space-y-2">
                              {selectedScenarioBudgetFlow.increased.length === 0 ? (
                                <div className="rounded-lg border border-emerald-100 bg-white px-3 py-2 text-sm text-slate-600">
                                  No markets with budget increase in this scenario.
                                </div>
                              ) : (
                                selectedScenarioBudgetFlow.increased.map((row) => {
                                  const shareWidth = Math.max(
                                    8,
                                    (Math.abs(row.budget_share_change_pct) / selectedScenarioBudgetFlow.maxShareDeltaPct) * 100,
                                  )
                                  const spendWidth = Math.max(
                                    8,
                                    (Math.abs(row.spend_delta_mn) / selectedScenarioBudgetFlow.maxSpendDeltaMn) * 100,
                                  )
                                  return (
                                    <button
                                      key={`inc-${selectedScenario.scenario_id}-${row.market}`}
                                      type="button"
                                      onClick={() => setScenarioMarketModal({ row, tone: 'increase' })}
                                      className="w-full rounded-lg border border-emerald-100 bg-white p-2.5 text-left shadow-sm transition-all duration-200 hover:shadow focus:outline-none focus:ring-2 focus:ring-emerald-200"
                                    >
                                      <div className="flex items-center justify-between gap-2">
                                        <p className="text-sm font-semibold text-dark-text">{row.market}</p>
                                        <p className="text-xs font-semibold text-emerald-700">{formatSignedPct(row.budget_share_change_pct, 2)}</p>
                                      </div>
                                      <div className="mt-1 grid gap-1 text-[11px] text-slate-600 sm:grid-cols-2">
                                        <p>Budget Share: {formatPct(row.old_budget_share_pct, 2)} {'->'} {formatPct(row.new_budget_share_pct, 2)}</p>
                                        <p>Spend Shift: <span className="font-semibold text-emerald-700">{formatSignedCurrencyMn(row.spend_delta_mn)}</span></p>
                                      </div>
                                      <div className="mt-2 space-y-1.5">
                                        <div>
                                          <div className="mb-0.5 flex items-center justify-between text-[10px] font-semibold uppercase tracking-wide text-slate-500">
                                            <span>Share Shift</span>
                                            <span>{formatSignedPct(row.budget_share_change_pct, 2)}</span>
                                          </div>
                                          <div className="h-1.5 w-full rounded-full bg-emerald-100">
                                            <div className="h-full rounded-full bg-emerald-500 transition-all duration-300" style={{ width: `${Math.min(100, shareWidth)}%` }} />
                                          </div>
                                        </div>
                                        <div>
                                          <div className="mb-0.5 flex items-center justify-between text-[10px] font-semibold uppercase tracking-wide text-slate-500">
                                            <span>Spend Shift (Mn)</span>
                                            <span>{formatSignedCurrencyMn(row.spend_delta_mn)}</span>
                                          </div>
                                          <div className="h-1.5 w-full rounded-full bg-emerald-100">
                                            <div className="h-full rounded-full bg-emerald-400 transition-all duration-300" style={{ width: `${Math.min(100, spendWidth)}%` }} />
                                          </div>
                                        </div>
                                      </div>
                                      <div className="mt-2 flex flex-wrap gap-1.5 text-[11px]">
                                        <span className={`rounded-full px-2 py-0.5 font-semibold ${row.tv_split_change_pct >= 0 ? 'bg-blue-100 text-blue-700' : 'bg-red-100 text-red-700'}`}>
                                          TV {formatSignedPct(row.tv_split_change_pct, 2)}
                                        </span>
                                        <span className={`rounded-full px-2 py-0.5 font-semibold ${row.digital_split_change_pct >= 0 ? 'bg-blue-100 text-blue-700' : 'bg-red-100 text-red-700'}`}>
                                          Digital {formatSignedPct(row.digital_split_change_pct, 2)}
                                        </span>
                                      </div>
                                    </button>
                                  )
                                })
                              )}
                            </div>
                          </div>

                          <div className="rounded-xl border border-rose-200 bg-rose-50/40 p-3">
                            <p className="text-xs font-semibold uppercase tracking-wide text-rose-700">Where Budget Decreased</p>
                            <div className="mt-2 space-y-2">
                              {selectedScenarioBudgetFlow.decreased.length === 0 ? (
                                <div className="rounded-lg border border-rose-100 bg-white px-3 py-2 text-sm text-slate-600">
                                  No markets with budget decrease in this scenario.
                                </div>
                              ) : (
                                selectedScenarioBudgetFlow.decreased.map((row) => {
                                  const shareWidth = Math.max(
                                    8,
                                    (Math.abs(row.budget_share_change_pct) / selectedScenarioBudgetFlow.maxShareDeltaPct) * 100,
                                  )
                                  const spendWidth = Math.max(
                                    8,
                                    (Math.abs(row.spend_delta_mn) / selectedScenarioBudgetFlow.maxSpendDeltaMn) * 100,
                                  )
                                  return (
                                    <button
                                      key={`dec-${selectedScenario.scenario_id}-${row.market}`}
                                      type="button"
                                      onClick={() => setScenarioMarketModal({ row, tone: 'decrease' })}
                                      className="w-full rounded-lg border border-rose-100 bg-white p-2.5 text-left shadow-sm transition-all duration-200 hover:shadow focus:outline-none focus:ring-2 focus:ring-rose-200"
                                    >
                                      <div className="flex items-center justify-between gap-2">
                                        <p className="text-sm font-semibold text-dark-text">{row.market}</p>
                                        <p className="text-xs font-semibold text-rose-700">{formatSignedPct(row.budget_share_change_pct, 2)}</p>
                                      </div>
                                      <div className="mt-1 grid gap-1 text-[11px] text-slate-600 sm:grid-cols-2">
                                        <p>Budget Share: {formatPct(row.old_budget_share_pct, 2)} {'->'} {formatPct(row.new_budget_share_pct, 2)}</p>
                                        <p>Spend Shift: <span className="font-semibold text-rose-700">{formatSignedCurrencyMn(row.spend_delta_mn)}</span></p>
                                      </div>
                                      <div className="mt-2 space-y-1.5">
                                        <div>
                                          <div className="mb-0.5 flex items-center justify-between text-[10px] font-semibold uppercase tracking-wide text-slate-500">
                                            <span>Share Shift</span>
                                            <span>{formatSignedPct(row.budget_share_change_pct, 2)}</span>
                                          </div>
                                          <div className="h-1.5 w-full rounded-full bg-rose-100">
                                            <div className="h-full rounded-full bg-rose-500 transition-all duration-300" style={{ width: `${Math.min(100, shareWidth)}%` }} />
                                          </div>
                                        </div>
                                        <div>
                                          <div className="mb-0.5 flex items-center justify-between text-[10px] font-semibold uppercase tracking-wide text-slate-500">
                                            <span>Spend Shift (Mn)</span>
                                            <span>{formatSignedCurrencyMn(row.spend_delta_mn)}</span>
                                          </div>
                                          <div className="h-1.5 w-full rounded-full bg-rose-100">
                                            <div className="h-full rounded-full bg-rose-400 transition-all duration-300" style={{ width: `${Math.min(100, spendWidth)}%` }} />
                                          </div>
                                        </div>
                                      </div>
                                      <div className="mt-2 flex flex-wrap gap-1.5 text-[11px]">
                                        <span className={`rounded-full px-2 py-0.5 font-semibold ${row.tv_split_change_pct >= 0 ? 'bg-blue-100 text-blue-700' : 'bg-red-100 text-red-700'}`}>
                                          TV {formatSignedPct(row.tv_split_change_pct, 2)}
                                        </span>
                                        <span className={`rounded-full px-2 py-0.5 font-semibold ${row.digital_split_change_pct >= 0 ? 'bg-blue-100 text-blue-700' : 'bg-red-100 text-red-700'}`}>
                                          Digital {formatSignedPct(row.digital_split_change_pct, 2)}
                                        </span>
                                      </div>
                                    </button>
                                  )
                                })
                              )}
                            </div>
                          </div>
                        </div>
                      </div>
                    ) : null}
                  </div>
                </section>
              ) : scenarioGenerationActive ? (
                <section className="rounded-xl border border-slate-200 bg-white p-6 shadow-panel">
                  <div className="rounded-xl border border-slate-200 bg-slate-50 px-5 py-6 sm:px-6">
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div>
                        <p className="text-xs font-semibold uppercase tracking-wide text-primary">Scenario Generation In Progress</p>
                        <p className="mt-1 text-sm font-semibold text-dark-text">
                          {scenarioMessage || 'Running AI + Monte Carlo engine...'}
                        </p>
                        <div className="mt-1 flex items-center gap-2 text-xs text-slate-500">
                          <span>Stage: {activeScenarioStage.label}</span>
                          <span className="h-1 w-1 rounded-full bg-slate-300" />
                          <span>Elapsed: {scenarioElapsedLabel}</span>
                        </div>
                      </div>
                      <div className="inline-flex items-center gap-2 rounded-full border border-blue-200 bg-blue-50 px-3 py-1.5">
                        <LoaderCircle className="h-4 w-4 animate-spin text-primary" />
                        <span className="text-sm font-semibold text-primary">{normalizedScenarioProgress}%</span>
                      </div>
                    </div>

                    <div className="relative mt-4 h-2.5 w-full overflow-hidden rounded-full bg-slate-200">
                      <div
                        className="h-full rounded-full bg-gradient-to-r from-blue-600 via-blue-500 to-indigo-500 transition-all duration-500"
                        style={{ width: `${normalizedScenarioProgress}%` }}
                      />
                      <div className="pointer-events-none absolute inset-0 animate-pulse bg-white/10" />
                    </div>

                    <div className="mt-4 grid gap-2 sm:grid-cols-2 xl:grid-cols-4">
                      {SCENARIO_PROGRESS_STAGES.map((stage, index) => {
                        const stageDone = normalizedScenarioProgress >= stage.end
                        const stageActive = index === activeScenarioStageIndex
                        return (
                          <div
                            key={`scenario-stage-${stage.key}`}
                            className={`rounded-lg border px-3 py-2 ${
                              stageDone
                                ? 'border-green-200 bg-green-50'
                                : stageActive
                                  ? 'border-blue-200 bg-blue-50'
                                  : 'border-slate-200 bg-white'
                            }`}
                          >
                            <div className="flex items-center gap-2">
                              {stageDone ? (
                                <CheckCircle2 className="h-4 w-4 text-success" />
                              ) : stageActive ? (
                                <LoaderCircle className="h-4 w-4 animate-spin text-primary" />
                              ) : (
                                <div className="h-2.5 w-2.5 rounded-full bg-slate-300" />
                              )}
                              <p className={`text-xs font-semibold uppercase tracking-wide ${stageDone ? 'text-success' : stageActive ? 'text-primary' : 'text-slate-500'}`}>
                                {stage.label}
                              </p>
                            </div>
                            <p className="mt-1 text-xs text-slate-600">{stage.hint}</p>
                          </div>
                        )
                      })}
                    </div>

                    <div className="mt-4 rounded-lg border border-slate-200 bg-white p-3">
                      <div className="flex items-center justify-between gap-2">
                        <div className="inline-flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-slate-500">
                          <Activity className="h-3.5 w-3.5 text-primary" />
                          Engine Activity
                        </div>
                        <div className="flex items-center gap-1.5">
                          <span className="h-2 w-2 rounded-full bg-primary animate-pulse" />
                          <span className="h-2 w-2 rounded-full bg-primary/80 animate-pulse" style={{ animationDelay: '160ms' }} />
                          <span className="h-2 w-2 rounded-full bg-primary/60 animate-pulse" style={{ animationDelay: '320ms' }} />
                        </div>
                      </div>
                      <div className="mt-2 space-y-2">
                        {scenarioActivityBars.map((bar) => (
                          <div key={`scenario-activity-${bar.key}`}>
                            <div className="mb-1 flex items-center justify-between text-[11px] text-slate-500">
                              <span>{bar.label}</span>
                              <span>{Math.round(bar.pct)}%</span>
                            </div>
                            <div className="h-1.5 w-full overflow-hidden rounded-full bg-slate-200">
                              <div
                                className="h-full rounded-full bg-primary/80 transition-all duration-500 animate-pulse"
                                style={{ width: `${bar.pct}%` }}
                              />
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                </section>
              ) : (
                <section className="rounded-xl border border-slate-200 bg-white p-6 shadow-panel">
                  <div className="rounded-xl border border-dashed border-slate-300 bg-slate-50 px-5 py-8 text-center">
                    <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Step 2</p>
                    <p className="mt-1 text-lg font-semibold text-dark-text">AI Scenario Lab</p>
                    <p className="mt-2 text-sm text-slate-600">Generate scenarios to explore volume and revenue outcomes by market.</p>
                  </div>
                </section>
              )
            ) : null}
            </div>
          )}
        </main>
      </div>
      {renderScenarioMarketModal()}
      {renderAiModeModal()}
    </div>
  )
}

export default App




