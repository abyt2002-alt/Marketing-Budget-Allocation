import { useEffect, useMemo, useState } from 'react'
import axios from 'axios'

type AutoConfigResponse = {
  brands: string[]
  markets_by_brand: Record<string, string[]>
  default_brand: string
  default_markets: string[]
}

type DebugInterpretationCondition = {
  metric_key: string
  metric_label: string
  kind: 'trend' | 'band'
  operator: string
  value: string | number
  source_text: string
  matched_markets?: string[]
}

type DebugRanking = {
  metric_key: string
  metric_label: string
  direction: 'ascending' | 'descending'
  limit: number
  source_text: string
  matched_markets?: string[]
}

type DebugComparison = {
  left_metric_key: string
  left_metric_label: string
  operator: '<' | '>'
  direction?: 'below' | 'above'
  right_metric_key: string
  right_metric_label: string
  source_text: string
  matched_markets?: string[]
}

type DebugExclusion = {
  market: string
  source_text: string
  matched_markets?: string[]
}

type DebugInterpretation = {
  goal: string
  task_types: string[]
  entity: string
  action_direction: string
  filters: DebugInterpretationCondition[]
  comparisons: DebugComparison[]
  rankings: DebugRanking[]
  exclusions: DebugExclusion[]
  execution_order: string[]
  assumptions: string[]
  reasoning: string
  matched_markets: string[]
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
  selection: {
    brand: string
    markets: string[]
    markets_count: number
  }
  market_intelligence_guidance: {
    source_file?: string | null
    matched_row_count?: number
    notes?: string[]
  }
  provider: string
  model: string
  ai_prompt: string
  raw_text: string
  parsed_json?: unknown
  normalized_interpretation?: DebugInterpretation
  hitl?: DebugHitl
  notes: string[]
}

type Props = {
  apiBaseUrl: string
  config: AutoConfigResponse | null
}

export function BudgetAllocationDebugPage({ apiBaseUrl, config }: Props) {
  const [debugBrand, setDebugBrand] = useState('')
  const [debugMarkets, setDebugMarkets] = useState<string[]>([])
  const [debugPrompt, setDebugPrompt] = useState('increase the spend where market share has reduced')
  const [debugLoading, setDebugLoading] = useState(false)
  const [debugError, setDebugError] = useState('')
  const [debugResult, setDebugResult] = useState<DebugResponse | null>(null)
  const [feedbackText, setFeedbackText] = useState('')
  const [feedbackLoading, setFeedbackLoading] = useState(false)
  const [approvalMessage, setApprovalMessage] = useState('')

  useEffect(() => {
    if (!config) return
    const nextBrand = config.default_brand || config.brands[0] || ''
    setDebugBrand(nextBrand)
    setDebugMarkets(config.markets_by_brand[nextBrand] ?? [])
  }, [config])

  const availableMarkets = useMemo(
    () => (debugBrand && config ? config.markets_by_brand[debugBrand] ?? [] : []),
    [config, debugBrand],
  )

  function toggleMarket(market: string) {
    setDebugMarkets((prev) => (prev.includes(market) ? prev.filter((item) => item !== market) : [...prev, market]))
  }

  async function runDebug(reviewMode: 'initial' | 'revise', userFeedback = '') {
    if (!debugBrand) {
      setDebugError('Select a brand first.')
      return
    }
    setApprovalMessage('')
    setDebugError('')
    if (reviewMode === 'initial') {
      setDebugLoading(true)
    } else {
      setFeedbackLoading(true)
    }
    try {
      const response = await axios.post<DebugResponse>(`${apiBaseUrl}/api/scenarios/intent/debug`, {
        selected_brand: debugBrand,
        selected_markets: debugMarkets,
        budget_increase_type: 'percentage',
        budget_increase_value: 5,
        market_overrides: {},
        intent_prompt: debugPrompt,
        review_mode: reviewMode,
        user_feedback: userFeedback,
        current_interpretation: debugResult?.normalized_interpretation ?? null,
      })
      setDebugResult(response.data)
      if (reviewMode === 'revise') {
        setFeedbackText('')
      }
    } catch (error) {
      if (axios.isAxiosError(error)) {
        setDebugError(error.response?.data?.detail ?? 'Failed to run Gemini debug.')
      } else {
        setDebugError('Unexpected error while running Gemini debug.')
      }
    } finally {
      setDebugLoading(false)
      setFeedbackLoading(false)
    }
  }

  function handleContinue() {
    const summary = debugResult?.hitl?.summary || 'Interpretation accepted.'
    setApprovalMessage(`Approved for next step. ${summary}`)
  }

  const interpretation = debugResult?.normalized_interpretation ?? null
  const hitl = debugResult?.hitl ?? null

  function filterSummary(condition: DebugInterpretationCondition) {
    if (condition.kind === 'trend') {
      return `${condition.metric_label} ${condition.operator === '<' ? 'is decreasing' : 'is increasing'}`
    }
    return `${condition.metric_label} ${condition.operator === '<=' ? 'is low' : 'is high'}`
  }

  return (
    <div className="w-full space-y-5">
      <section className="budget-panel p-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <p className="budget-kicker">Budget Allocation 2.0</p>
            <h2 className="mt-2 text-2xl font-semibold tracking-tight text-slate-950">Prompt Interpreter + HITL</h2>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-600">
              This page is only for prompt understanding. Gemini proposes the interpretation, code normalizes it against the 5 supported columns, and you can continue or send feedback to revise it.
            </p>
          </div>
          <div className="rounded-full border border-[#d7cbb7] bg-[#fbf8f1] px-4 py-2 text-xs font-semibold uppercase tracking-[0.16em] text-[#8c7554]">
            Separate 2.0 Lane
          </div>
        </div>
      </section>

      <section className="grid gap-5 xl:grid-cols-[420px_minmax(0,1fr)]">
        <div className="budget-panel space-y-4 p-5">
          <div>
            <label className="budget-label">Brand</label>
            <select
              value={debugBrand}
              onChange={(event) => {
                const nextBrand = event.target.value
                setDebugBrand(nextBrand)
                setDebugMarkets(config?.markets_by_brand[nextBrand] ?? [])
              }}
              className="mt-1.5 w-full rounded-xl border border-[#d7cbb7] bg-white px-3 py-2.5 text-sm text-slate-700 shadow-sm outline-none transition focus:border-[#8b6a3f] focus:ring-4 focus:ring-[#c9b79b]/30"
            >
              {(config?.brands ?? []).map((brand) => (
                <option key={brand} value={brand}>
                  {brand}
                </option>
              ))}
            </select>
          </div>

          <div>
            <div className="flex items-center justify-between gap-2">
              <label className="budget-label">Markets</label>
              <button
                type="button"
                onClick={() => setDebugMarkets(availableMarkets)}
                className="rounded-full border border-[#d7cbb7] bg-white px-3 py-1 text-[11px] font-semibold uppercase tracking-wide text-slate-600"
              >
                All
              </button>
            </div>
            <div className="mt-2 max-h-64 space-y-1 overflow-y-auto rounded-[18px] border border-[#ece4d6] bg-[#fbf8f1] p-2.5">
              {availableMarkets.map((market) => (
                <label
                  key={`debug-market-${market}`}
                  className={`flex cursor-pointer items-center justify-between rounded-xl border px-3 py-2 text-sm transition ${
                    debugMarkets.includes(market)
                      ? 'border-[#9c7a4a] bg-[#f4ece0] text-[#7a5b31]'
                      : 'border-[#ece4d6] bg-white text-slate-700'
                  }`}
                >
                  <span>{market}</span>
                  <input
                    type="checkbox"
                    checked={debugMarkets.includes(market)}
                    onChange={() => toggleMarket(market)}
                    className="h-4 w-4 rounded border-slate-300 text-primary"
                  />
                </label>
              ))}
            </div>
          </div>

          <div>
            <label className="budget-label">Prompt</label>
            <textarea
              rows={5}
              value={debugPrompt}
              onChange={(event) => setDebugPrompt(event.target.value)}
              className="mt-1.5 w-full resize-none rounded-[18px] border border-[#d7cbb7] bg-white px-3 py-2.5 text-sm leading-6 text-slate-700 shadow-sm outline-none transition focus:border-[#8b6a3f] focus:ring-4 focus:ring-[#c9b79b]/30"
            />
          </div>

          <button
            type="button"
            onClick={() => runDebug('initial')}
            disabled={debugLoading || !debugPrompt.trim()}
            className="w-full rounded-full bg-[#7b5c33] px-5 py-3 text-sm font-semibold text-white shadow-lg shadow-[#7b5c33]/15 transition hover:bg-[#6c4f2a] disabled:cursor-not-allowed disabled:bg-slate-400 disabled:shadow-none"
          >
            {debugLoading ? 'Interpreting...' : 'Interpret Prompt'}
          </button>

          {debugError ? (
            <div className="rounded-[18px] border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{debugError}</div>
          ) : null}
          {approvalMessage ? (
            <div className="rounded-[18px] border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-700">{approvalMessage}</div>
          ) : null}
        </div>

        <div className="space-y-5">
          <section className="budget-panel p-5">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <p className="budget-label">What 2.0 Understood</p>
                <p className="mt-2 text-sm leading-6 text-slate-600">
                  Gemini proposes the meaning. The backend then normalizes it into one of the supported metrics and computes matched markets in code.
                </p>
              </div>
              {hitl ? (
                <div className={`rounded-full px-4 py-2 text-xs font-semibold uppercase tracking-[0.16em] ${hitl.needs_review ? 'border border-amber-200 bg-amber-50 text-amber-700' : 'border border-emerald-200 bg-emerald-50 text-emerald-700'}`}>
                  Confidence {Math.round(hitl.confidence * 100)}%
                </div>
              ) : null}
            </div>

            {interpretation ? (
              <div className="mt-4 space-y-4">
                <div className="rounded-[18px] border border-[#e3d8c4] bg-[#fbf8f1] p-4">
                  <p className="text-sm font-semibold text-dark-text">{hitl?.summary}</p>
                  <div className="mt-3 flex flex-wrap gap-2 text-xs">
                    <span className="rounded-full bg-white px-3 py-1 font-semibold text-slate-700">Action: {interpretation.action_direction}</span>
                    <span className="rounded-full bg-white px-3 py-1 font-semibold text-slate-700">Task: {(interpretation.task_types || []).join(', ') || 'n/a'}</span>
                    <span className="rounded-full bg-white px-3 py-1 font-semibold text-slate-700">Entity: {interpretation.entity}</span>
                  </div>
                </div>

                <div className="rounded-[18px] border border-[#e3d8c4] bg-white p-4">
                  <p className="text-xs font-semibold uppercase tracking-[0.18em] text-[#8c7554]">Execution Order</p>
                  <div className="mt-3 flex flex-wrap gap-2">
                    {(interpretation.execution_order || []).length > 0 ? (
                      interpretation.execution_order.map((step) => (
                        <span key={step} className="rounded-full bg-[#f4ece0] px-3 py-1 text-sm font-semibold text-[#7a5b31]">
                          {step}
                        </span>
                      ))
                    ) : (
                      <p className="text-sm text-slate-500">No execution order provided.</p>
                    )}
                  </div>
                </div>

                {(interpretation.rankings || []).map((ranking, index) => (
                  <div key={`ranking-${index}`} className="rounded-[18px] border border-blue-200 bg-blue-50/60 p-4">
                    <p className="text-xs font-semibold uppercase tracking-[0.18em] text-blue-700">Ranking {index + 1}</p>
                    <p className="mt-2 text-sm text-slate-700">
                      Top {ranking.limit} by {ranking.metric_label} ({ranking.metric_key})
                    </p>
                    <p className="mt-1 text-xs text-slate-500">Direction: {ranking.direction}</p>
                  </div>
                ))}

                {(interpretation.exclusions || []).map((exclusion, index) => (
                  <div key={`exclusion-${index}`} className="rounded-[18px] border border-rose-200 bg-rose-50/60 p-4">
                    <p className="text-xs font-semibold uppercase tracking-[0.18em] text-rose-700">Exclusion {index + 1}</p>
                    <p className="mt-2 text-sm text-slate-700">Exclude market: {exclusion.market}</p>
                  </div>
                ))}

                {(interpretation.comparisons || []).map((comparison, index) => (
                  <div key={`comparison-${index}`} className="rounded-[18px] border border-violet-200 bg-violet-50/60 p-4">
                    <p className="text-xs font-semibold uppercase tracking-[0.18em] text-violet-700">Comparison {index + 1}</p>
                    <p className="mt-2 text-sm text-slate-700">
                      {comparison.left_metric_label} ({comparison.left_metric_key}) {comparison.operator} {comparison.right_metric_label} ({comparison.right_metric_key})
                    </p>
                    <p className="mt-1 text-xs text-slate-500">Direction: {comparison.direction || (comparison.operator === '<' ? 'below' : 'above')}</p>
                  </div>
                ))}

                {(interpretation.filters || []).map((condition, index) => (
                  <div key={`condition-${index}`} className="rounded-[18px] border border-[#e3d8c4] bg-white p-4">
                    <p className="text-xs font-semibold uppercase tracking-[0.18em] text-[#8c7554]">Filter {index + 1}</p>
                    <p className="mt-2 text-sm text-slate-700">{filterSummary(condition)}</p>
                    <p className="mt-1 text-xs text-slate-500">
                      Kind: {condition.kind} | Operator: {condition.operator} | Value: {String(condition.value)}
                    </p>
                  </div>
                ))}

                <div className="rounded-[18px] border border-[#e3d8c4] bg-white p-4">
                  <p className="text-xs font-semibold uppercase tracking-[0.18em] text-[#8c7554]">Matched Markets</p>
                  <div className="mt-3 flex flex-wrap gap-2">
                    {(interpretation.matched_markets || []).length > 0 ? (
                      interpretation.matched_markets.map((market) => (
                        <span key={market} className="rounded-full bg-[#f4ece0] px-3 py-1 text-sm font-semibold text-[#7a5b31]">
                          {market}
                        </span>
                      ))
                    ) : (
                      <p className="text-sm text-slate-500">No matched markets.</p>
                    )}
                  </div>
                </div>

                <div className="rounded-[18px] border border-[#e3d8c4] bg-white p-4">
                  <p className="text-xs font-semibold uppercase tracking-[0.18em] text-[#8c7554]">Gemini Reasoning</p>
                  <p className="mt-3 text-sm leading-6 text-slate-700">
                    {interpretation.reasoning?.trim() || 'No reasoning was returned by Gemini.'}
                  </p>
                </div>

                {(hitl?.review_reason || []).length > 0 ? (
                  <div className="rounded-[18px] border border-amber-200 bg-amber-50 p-4">
                    <p className="text-xs font-semibold uppercase tracking-[0.18em] text-amber-700">Why Review Is Suggested</p>
                    <div className="mt-2 space-y-2">
                      {hitl?.review_reason.map((reason, index) => (
                        <p key={`review-reason-${index}`} className="text-sm text-amber-800">
                          {reason}
                        </p>
                      ))}
                    </div>
                  </div>
                ) : null}

                <div className="rounded-[18px] border border-[#e3d8c4] bg-[#fcfaf6] p-4">
                  <p className="text-xs font-semibold uppercase tracking-[0.18em] text-[#8c7554]">HITL Review</p>
                  <div className="mt-3 flex flex-wrap gap-3">
                    <button
                      type="button"
                      onClick={handleContinue}
                      className="rounded-full bg-emerald-600 px-4 py-2 text-sm font-semibold text-white transition hover:bg-emerald-700"
                    >
                      Continue With This
                    </button>
                  </div>
                  <div className="mt-4">
                    <label className="budget-label">Give Feedback To Gemini</label>
                    <textarea
                      rows={4}
                      value={feedbackText}
                      onChange={(event) => setFeedbackText(event.target.value)}
                      placeholder="Example: I meant top 7 markets by category salience, not low category salience."
                      className="mt-1.5 w-full resize-none rounded-[18px] border border-[#d7cbb7] bg-white px-3 py-2.5 text-sm leading-6 text-slate-700 shadow-sm outline-none transition focus:border-[#8b6a3f] focus:ring-4 focus:ring-[#c9b79b]/30"
                    />
                    <button
                      type="button"
                      onClick={() => runDebug('revise', feedbackText)}
                      disabled={feedbackLoading || !feedbackText.trim()}
                      className="mt-3 rounded-full bg-[#7b5c33] px-4 py-2 text-sm font-semibold text-white transition hover:bg-[#6c4f2a] disabled:cursor-not-allowed disabled:bg-slate-400"
                    >
                      {feedbackLoading ? 'Revising...' : 'Revise Interpretation'}
                    </button>
                  </div>
                </div>
              </div>
            ) : (
              <p className="mt-3 text-sm text-slate-500">Run a prompt to inspect the interpretation.</p>
            )}
          </section>

          <section className="budget-panel p-5">
            <p className="budget-label">Execution Context</p>
            {debugResult ? (
              <div className="mt-3 space-y-2 text-sm text-slate-700">
                <p>
                  Brand: <span className="font-semibold text-dark-text">{debugResult.selection.brand}</span>
                </p>
                <p>
                  Markets: <span className="font-semibold text-dark-text">{debugResult.selection.markets_count}</span>
                </p>
                <p>
                  Intelligence rows matched:{' '}
                  <span className="font-semibold text-dark-text">{debugResult.market_intelligence_guidance?.matched_row_count ?? 0}</span>
                </p>
              </div>
            ) : (
              <p className="mt-3 text-sm text-slate-500">Run a prompt to inspect the Gemini response context.</p>
            )}
          </section>

          <section className="grid gap-5 xl:grid-cols-2">
            <div className="budget-panel p-5">
              <p className="budget-label">Raw Gemini Text</p>
              <pre className="mt-3 max-h-[360px] overflow-auto rounded-[18px] border border-[#ece4d6] bg-[#fbf8f1] p-4 text-xs leading-6 text-slate-700 whitespace-pre-wrap">
                {debugResult?.raw_text || 'No raw Gemini response yet.'}
              </pre>
            </div>
            <div className="budget-panel p-5">
              <p className="budget-label">Parsed JSON</p>
              <pre className="mt-3 max-h-[360px] overflow-auto rounded-[18px] border border-[#ece4d6] bg-[#fbf8f1] p-4 text-xs leading-6 text-slate-700 whitespace-pre-wrap">
                {debugResult?.parsed_json ? JSON.stringify(debugResult.parsed_json, null, 2) : 'No parsed JSON yet.'}
              </pre>
            </div>
          </section>

          <section className="grid gap-5 xl:grid-cols-2">
            <div className="budget-panel p-5">
              <p className="budget-label">Prompt Sent To Gemini</p>
              <pre className="mt-3 max-h-[320px] overflow-auto rounded-[18px] border border-[#ece4d6] bg-[#fbf8f1] p-4 text-xs leading-6 text-slate-700 whitespace-pre-wrap">
                {debugResult?.ai_prompt || 'No debug prompt sent yet.'}
              </pre>
            </div>
            <div className="budget-panel p-5">
              <p className="budget-label">Backend Notes</p>
              <div className="mt-3 space-y-2">
                {(debugResult?.notes ?? []).length > 0 ? (
                  (debugResult?.notes ?? []).map((note, index) => (
                    <p key={`debug-note-${index}`} className="text-sm leading-6 text-slate-700">
                      {note}
                    </p>
                  ))
                ) : (
                  <p className="text-sm text-slate-500">No backend notes yet.</p>
                )}
              </div>
            </div>
          </section>
        </div>
      </section>
    </div>
  )
}
