export const DEFAULT_SAVED_SCENARIOS_KEY = 'saved_scenarios_v1'
export const DEFAULT_SAVED_SCENARIOS_MAX = 200
export const SAVED_SCHEMA_VERSION = 1

export type SavedItemSummary = {
  selected_brand: string
  markets_count: number
  scenario_count: number
  scenario_id: string | null
  revenue_uplift_pct: number | null
  budget_utilized: number | null
}

export type SavedItem<TPayload = unknown> = {
  id: string
  schemaVersion: number
  name: string
  savedAt: string
  savedAtLabel: string
  summary: SavedItemSummary
  payload: TPayload
}

function toSavedAtLabel(savedAtIso: string) {
  const date = new Date(savedAtIso)
  if (Number.isNaN(date.getTime())) return savedAtIso
  return date.toLocaleString('en-IN', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value != null
}

export function readSavedItems<TPayload = unknown>(
  storageKey = DEFAULT_SAVED_SCENARIOS_KEY,
): SavedItem<TPayload>[] {
  if (typeof window === 'undefined') return []
  try {
    const raw = window.localStorage.getItem(storageKey)
    if (!raw) return []
    const parsed = JSON.parse(raw) as unknown
    if (!Array.isArray(parsed)) return []
    return parsed
      .filter((item) => isRecord(item))
      .map((item) => {
        const id = typeof item.id === 'string' ? item.id : ''
        const schemaVersion = typeof item.schemaVersion === 'number' ? item.schemaVersion : SAVED_SCHEMA_VERSION
        const name = typeof item.name === 'string' ? item.name : 'Plan'
        const savedAt = typeof item.savedAt === 'string' ? item.savedAt : new Date().toISOString()
        const savedAtLabel =
          typeof item.savedAtLabel === 'string' && item.savedAtLabel.trim().length > 0
            ? item.savedAtLabel
            : toSavedAtLabel(savedAt)
        const summary = isRecord(item.summary) ? item.summary : {}
        const payload = (item.payload as TPayload | undefined) ?? ({} as TPayload)
        return {
          id,
          schemaVersion,
          name,
          savedAt,
          savedAtLabel,
          summary: {
            selected_brand:
              typeof summary.selected_brand === 'string' ? summary.selected_brand : '',
            markets_count:
              typeof summary.markets_count === 'number' ? summary.markets_count : 0,
            scenario_count:
              typeof summary.scenario_count === 'number' ? summary.scenario_count : 0,
            scenario_id:
              typeof summary.scenario_id === 'string' ? summary.scenario_id : null,
            revenue_uplift_pct:
              typeof summary.revenue_uplift_pct === 'number'
                ? summary.revenue_uplift_pct
                : null,
            budget_utilized:
              typeof summary.budget_utilized === 'number' ? summary.budget_utilized : null,
          },
          payload,
        } satisfies SavedItem<TPayload>
      })
      .filter((item) => item.id.length > 0 && item.schemaVersion === SAVED_SCHEMA_VERSION)
  } catch {
    return []
  }
}

export function writeSavedItems<TPayload = unknown>(
  items: SavedItem<TPayload>[],
  storageKey = DEFAULT_SAVED_SCENARIOS_KEY,
) {
  if (typeof window === 'undefined') return
  window.localStorage.setItem(storageKey, JSON.stringify(items))
}

export function nextPlanName<TPayload = unknown>(items: SavedItem<TPayload>[]) {
  const maxNum = items.reduce((acc, item) => {
    const match = item.name.match(/^Plan\s+(\d+)$/i)
    if (!match) return acc
    const num = Number(match[1])
    return Number.isFinite(num) ? Math.max(acc, num) : acc
  }, 0)
  return `Plan ${maxNum + 1}`
}

export function buildSavedItem<TPayload = unknown>(params: {
  name: string
  summary: SavedItemSummary
  payload: TPayload
}): SavedItem<TPayload> {
  const savedAt = new Date().toISOString()
  const id =
    typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function'
      ? crypto.randomUUID()
      : `${Date.now()}-${Math.random().toString(16).slice(2)}`
  return {
    id,
    schemaVersion: SAVED_SCHEMA_VERSION,
    name: params.name,
    savedAt,
    savedAtLabel: toSavedAtLabel(savedAt),
    summary: params.summary,
    payload: params.payload,
  }
}

