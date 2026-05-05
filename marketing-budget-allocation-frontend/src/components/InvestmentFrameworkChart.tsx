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
    description: 'Increase investments up to maximum level of impact to fuel brand growth.',
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

export function InvestmentFrameworkChart({ data, displayBrandName }: Props) {
  const { markets, thresholds } = data

  const byQuadrant = Object.fromEntries(
    (Object.keys(Q) as QuadrantKey[]).map((k) => [
      k,
      [...markets.filter((m) => m.quadrant === k)].sort((a, b) => b.brand_salience - a.brand_salience),
    ])
  ) as Record<QuadrantKey, FrameworkMarket[]>

  const elMax = thresholds.elasticity_max

  const quadrantOrder: QuadrantKey[][] = [
    ['maintain_salience', 'increase'],
    ['scale_back', 'maintain_elasticity'],
  ]

  return (
    <div className="space-y-5" aria-label={`${displayBrandName} investment framework`}>
      {/* 2×2 grid */}
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
                    const salPct = Math.round(m.brand_salience * 100)
                    const elPct = Math.round((m.overall_media_elasticity / elMax) * 100)
                    const name = DISPLAY[m.market] ?? m.market
                    const yoy = m.yoy_pct
                    return (
                      <div
                        key={m.market}
                        className="flex items-center gap-2 rounded-lg border px-2.5 py-1.5"
                        style={{ background: cfg.pillBg, borderColor: cfg.pillBorder }}
                      >
                        <span className="text-[12px] font-semibold" style={{ color: cfg.pillText }}>
                          {name}
                        </span>
                        <span className="flex gap-1 text-[10px] font-medium text-slate-400">
                          <span title="Brand Salience">S {salPct}%</span>
                          <span>·</span>
                          <span title="Media Elasticity">E {elPct}%</span>
                          {yoy != null && (
                            <>
                              <span>·</span>
                              <span title="YoY Volume Growth FY24→FY25" className="font-semibold" style={{ color: yoy >= 0 ? '#16a34a' : '#dc2626' }}>
                                {yoy >= 0 ? '+' : ''}{yoy}%
                              </span>
                            </>
                          )}
                        </span>
                      </div>
                    )
                  })
                )}
              </div>
            </div>
          )
        })}
      </div>

      {/* Footer note */}
      <p className="text-center text-[11px] text-slate-400">
        S = Brand Salience · E = Media Elasticity relative to max · Split at median of each dimension
      </p>
    </div>
  )
}
