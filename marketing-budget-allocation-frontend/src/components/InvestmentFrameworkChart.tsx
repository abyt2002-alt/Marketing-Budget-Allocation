import { ArrowUpRight, Minus, ArrowDownRight } from 'lucide-react'

export interface FrameworkMarket {
  market: string
  category_salience: number
  brand_salience: number
  overall_media_elasticity: number
  quadrant: 'increase' | 'maintain_salience' | 'maintain_elasticity' | 'scale_back'
  yoy_pct?: number | null
}

export interface FrameworkThresholds {
  salience_median: number
  elasticity_median: number
  salience_min: number
  salience_max: number
  elasticity_min: number
  elasticity_max: number
}

export interface InvestmentFrameworkData {
  status: string
  brand: string
  markets: FrameworkMarket[]
  thresholds: FrameworkThresholds
}

interface Props {
  data: InvestmentFrameworkData
  displayBrandName: string
  quadrantNotes?: Partial<Record<FrameworkMarket['quadrant'], string>>
  onMarketClick?: (market: FrameworkMarket) => void
}

const Q = {
  maintain_salience: {
    bg: '#FFFBEB',
    border: '#FDE68A',
    pillBg: '#FEF3C7',
    pillBorder: '#FCD34D',
    pillText: '#92400E',
    accent: '#FFBD59',
    label: 'MAINTAIN',
    position: 'High Salience · Low Elasticity',
    description: 'Media-led brand growth is limited. Maintain current levels to protect share.',
    icon: Minus,
    iconColor: '#B45309',
    row: 0,
    col: 0,
  },
  increase: {
    bg: '#F0FDF4',
    border: '#BBF7D0',
    pillBg: '#DCFCE7',
    pillBorder: '#86EFAC',
    pillText: '#166534',
    accent: '#41C185',
    label: 'INCREASE MEDIA',
    position: 'High Salience · High Elasticity',
    description: 'Increase investments up to maximum level of impact to fuel category growth.',
    icon: ArrowUpRight,
    iconColor: '#166534',
    row: 0,
    col: 1,
  },
  scale_back: {
    bg: '#FFF1F2',
    border: '#FECDD3',
    pillBg: '#FFE4E6',
    pillBorder: '#FCA5A5',
    pillText: '#9F1239',
    accent: '#F87171',
    label: 'SCALE BACK',
    position: 'Low Salience · Low Elasticity',
    description: 'Scale back to minimum Reach level and reallocate funds to higher-priority markets.',
    icon: ArrowDownRight,
    iconColor: '#9F1239',
    row: 1,
    col: 0,
  },
  maintain_elasticity: {
    bg: '#EFF6FF',
    border: '#BFDBFE',
    pillBg: '#DBEAFE',
    pillBorder: '#93C5FD',
    pillText: '#1E40AF',
    accent: '#458EE2',
    label: 'MAINTAIN',
    position: 'Low Salience · High Elasticity',
    description: 'Market is small. Media responsiveness is high but additional investment is not required.',
    icon: Minus,
    iconColor: '#1E40AF',
    row: 1,
    col: 1,
  },
} as const

type QuadrantKey = keyof typeof Q

const DISPLAY: Record<string, string> = {
  'Bihar-Jharkhand': 'Bihar-Jharkhand',
  'MP-Chhattisgarh': 'MP-Chhattisgarh',
  'PunHarHPJK': 'Punjab / Har / HP',
  'Andhra-Telangana': 'Andhra-Telangana',
}

export function InvestmentFrameworkChart({ data, displayBrandName, quadrantNotes, onMarketClick }: Props) {
  const { markets } = data

  const byQuadrant = Object.fromEntries(
    (Object.keys(Q) as QuadrantKey[]).map((k) => [
      k,
      [...markets.filter((m) => m.quadrant === k)].sort((a, b) => b.category_salience - a.category_salience),
    ])
  ) as Record<QuadrantKey, FrameworkMarket[]>

  const quadrantOrder: QuadrantKey[][] = [
    ['maintain_salience', 'increase'],
    ['scale_back', 'maintain_elasticity'],
  ]

  return (
    <div className="space-y-5" aria-label={`${displayBrandName} investment framework`}>

      {/* Axis labels row — Elasticity (X-axis) */}
      <div className="hidden md:flex items-center gap-2 px-1">
        <div className="flex flex-1 items-center gap-2">
          <div className="h-px flex-1 bg-slate-300" />
          <span className="whitespace-nowrap rounded-full border border-slate-300 bg-white px-3 py-0.5 text-[10px] font-bold uppercase tracking-widest text-slate-500">
            ← Low Elasticity
          </span>
          <div className="w-4 text-center text-slate-300 text-xs">|</div>
          <span className="whitespace-nowrap rounded-full border border-slate-300 bg-white px-3 py-0.5 text-[10px] font-bold uppercase tracking-widest text-slate-500">
            High Elasticity →
          </span>
          <div className="h-px flex-1 bg-slate-300" />
        </div>
      </div>

      {/* 2×2 grid with Y-axis label */}
      <div className="flex gap-0">
        {/* Y-axis: one label per row */}
        <div className="hidden md:flex w-24 flex-shrink-0 flex-col gap-3 pr-2">
          <div className="flex flex-1 items-center justify-end">
            <span className="whitespace-nowrap rounded-full border border-slate-300 bg-white px-2.5 py-0.5 text-[10px] font-bold uppercase tracking-widest text-slate-500">
              ↑ High Sal
            </span>
          </div>
          <div className="flex flex-1 items-center justify-end">
            <span className="whitespace-nowrap rounded-full border border-slate-300 bg-white px-2.5 py-0.5 text-[10px] font-bold uppercase tracking-widest text-slate-500">
              ↓ Low Sal
            </span>
          </div>
        </div>

        <div className="flex-1 min-w-0">
          <div className="grid grid-cols-2 gap-3">
          {quadrantOrder.flat().map((qKey) => {
          const cfg = Q[qKey]
          const Icon = cfg.icon
          const mktList = byQuadrant[qKey] ?? []

          return (
            <div
              key={qKey}
              className="rounded-xl border p-4"
              style={{ background: cfg.bg, borderColor: cfg.border }}
            >
              {/* Quadrant header */}
              <div className="flex items-start justify-between gap-2">
                <div>
                  <div className="flex items-center gap-1.5">
                    <Icon className="h-3.5 w-3.5 flex-shrink-0" style={{ color: cfg.iconColor }} />
                    <p className="text-[11px] font-black uppercase tracking-widest" style={{ color: cfg.iconColor }}>
                      {cfg.label}
                    </p>
                  </div>
                  <p className="mt-0.5 text-[10px] font-medium text-slate-400 uppercase tracking-wide">
                    {cfg.position}
                  </p>
                </div>
                <span
                  className="flex-shrink-0 rounded-full px-2 py-0.5 text-[11px] font-bold"
                  style={{ background: cfg.pillBg, color: cfg.iconColor }}
                >
                  {mktList.length}
                </span>
              </div>

              <p className="mt-2 text-[11px] leading-relaxed text-slate-500 border-t pt-2" style={{ borderColor: cfg.border }}>
                {cfg.description}
              </p>

              {/* Market pills */}
              <div className="mt-3 flex flex-wrap gap-1.5">
                {mktList.length === 0 ? (
                  <span className="text-[11px] text-slate-400 italic">No markets in this quadrant</span>
                ) : (
                  mktList.map((m) => {
                    const salValue = m.category_salience.toFixed(2)
                    const elPct = m.overall_media_elasticity.toFixed(2)
                    const name = DISPLAY[m.market] ?? m.market
                    return (
                      <button
                        type="button"
                        key={m.market}
                        onClick={() => onMarketClick?.(m)}
                        className={`flex items-center gap-2 rounded-lg border px-2.5 py-1.5 text-left transition ${onMarketClick ? 'hover:brightness-95 focus:outline-none focus:ring-2 focus:ring-blue-200' : ''}`}
                        style={{ background: cfg.pillBg, borderColor: cfg.pillBorder }}
                      >
                        <span className="text-[12px] font-semibold" style={{ color: cfg.pillText }}>
                          {name}
                        </span>
                        <span className="flex gap-1 text-[10px] font-extrabold" style={{ color: cfg.iconColor }}>
                          <span title="Category Salience">S {salValue}</span>
                          <span className="opacity-50">·</span>
                          <span title="Media Elasticity">E {elPct}</span>
                        </span>
                      </button>
                    )
                  })
                )}
              </div>

              {quadrantNotes?.[qKey] ? (
                <p
                  className="mt-3 rounded-lg border px-3 py-2 text-[11px] leading-relaxed"
                  style={{ borderColor: cfg.pillBorder, background: '#FFFFFF99', color: cfg.pillText }}
                >
                  {quadrantNotes[qKey]}
                </p>
              ) : null}
            </div>
          )
          })}
          </div>
        </div>
      </div>

      {/* Footer note */}

      <p className="text-center text-[11px] text-slate-400">
        S = Category Salience · E = Media Elasticity · Split at median of each dimension
      </p>
    </div>
  )
}
