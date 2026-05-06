import { ComposableMap, Geographies, Geography, Marker } from 'react-simple-maps'
import type { FrameworkMarket } from './InvestmentFrameworkChart'

interface Props {
  markets: FrameworkMarket[]
  onMarketClick?: (market: FrameworkMarket) => void
  nationalElasticity?: number | null
  nationalYoy?: number | null
}

const INDIA_GEO = '/india_states.geojson'

const STATE_TO_MARKET: Record<string, string> = {
  'Rajasthan':          'Rajasthan',
  'Gujarat':            'Gujarat',
  'Maharashtra':        'Maharashtra',
  'Madhya Pradesh':     'MP-Chhattisgarh',
  'Chhattisgarh':       'MP-Chhattisgarh',
  'Karnataka':          'Karnataka',
  'Tamil Nadu':         'Tamil Nadu',
  'Kerala':             'Kerala',
  'Andhra Pradesh':     'Andhra-Telangana',
  'Telangana':          'Andhra-Telangana',
  'West Bengal':        'West Bengal',
  'Bihar':              'Bihar-Jharkhand',
  'Jharkhand':          'Bihar-Jharkhand',
  'Odisha':             'Odisha',
  'Uttar Pradesh':      'UP-UK',
  'Uttarakhand':        'UP-UK',
  'NCT of Delhi':       'Delhi-NCR',
  'Delhi':              'Delhi-NCR',
  'Haryana':            'PunHarHPJK',
  'Punjab':             'PunHarHPJK',
  'Himachal Pradesh':   'PunHarHPJK',
  'Jammu & Kashmir':    'PunHarHPJK',
  'Jammu and Kashmir':  'PunHarHPJK',
  'Ladakh':             'PunHarHPJK',
  'Assam':              'Assam-NE',
  'Meghalaya':          'Assam-NE',
  'Manipur':            'Assam-NE',
  'Mizoram':            'Assam-NE',
  'Nagaland':           'Assam-NE',
  'Tripura':            'Assam-NE',
  'Arunachal Pradesh':  'Assam-NE',
  'Sikkim':             'Assam-NE',
}

const CENTROIDS: Record<string, [number, number]> = {
  'Delhi-NCR':         [77.1,  28.7],
  'Maharashtra':       [75.7,  19.5],
  'PunHarHPJK':        [75.3,  31.0],
  'Gujarat':           [71.5,  22.5],
  'Karnataka':         [76.3,  15.0],
  'Andhra-Telangana':  [79.5,  17.5],
  'Tamil Nadu':        [78.5,  11.0],
  'UP-UK':             [80.5,  27.3],
  'MP-Chhattisgarh':   [80.5,  22.0],
  'West Bengal':       [87.5,  23.5],
  'Rajasthan':         [73.5,  27.0],
  'Kerala':            [76.2,   9.6],
  'Bihar-Jharkhand':   [85.5,  24.0],
  'Odisha':            [84.5,  20.5],
  'Assam-NE':          [92.5,  26.2],
}

const DISPLAY: Record<string, string> = {
  'PunHarHPJK':       'Pun/HP/JK',
  'Andhra-Telangana': 'AP-TS',
  'MP-Chhattisgarh':  'MP-CG',
  'Bihar-Jharkhand':  'Bihar-JK',
  'West Bengal':      'WB',
  'Tamil Nadu':       'TN',
  'Assam-NE':         'Assam-NE',
  'Maharashtra':      'MH',
  'Karnataka':        'KA',
  'Gujarat':          'GJ',
  'Rajasthan':        'RJ',
  'Kerala':           'KL',
  'Odisha':           'OD',
  'UP-UK':            'UP-UK',
  'Delhi-NCR':        'Delhi',
}

const Q_COLORS: Record<string, { fill: string; stroke: string; legend: string }> = {
  increase:            { fill: '#41C185', stroke: '#14532d', legend: '↑ Increase' },
  maintain_salience:   { fill: '#FFBD59', stroke: '#78350f', legend: '— Hold / Protect' },
  maintain_elasticity: { fill: '#458EE2', stroke: '#1e3a8a', legend: '◎ Selective Test' },
  scale_back:          { fill: '#F87171', stroke: '#7f1d1d', legend: '↓ Scale Back' },
}

export function IndiaMapChart({ markets, onMarketClick, nationalElasticity, nationalYoy }: Props) {
  const marketByKey = Object.fromEntries(markets.map((m) => [m.market, m]))
  const salMax = Math.max(...markets.map((m) => m.category_salience), 0.001)
  const legendItems = (Object.entries(Q_COLORS) as [string, typeof Q_COLORS[string]][])
    .filter(([k]) => markets.some((m) => m.quadrant === k))

  // Derived national stats from markets when not explicitly passed
  const validYoys = markets.map((m) => m.yoy_pct).filter((v): v is number => v != null)
  const avgYoy = validYoys.length > 0 ? validYoys.reduce((a, b) => a + b, 0) / validYoys.length : null
  const displayYoy = nationalYoy ?? avgYoy
  const displayElasticity = nationalElasticity ?? null

  const quadrantCounts = {
    increase: markets.filter((m) => m.quadrant === 'increase').length,
    maintain_salience: markets.filter((m) => m.quadrant === 'maintain_salience').length,
    maintain_elasticity: markets.filter((m) => m.quadrant === 'maintain_elasticity').length,
    scale_back: markets.filter((m) => m.quadrant === 'scale_back').length,
  }

  const getStyle = (props: Record<string, string>) => {
    const name = props.ST_NM || ''
    const marketKey = STATE_TO_MARKET[name]
    const market = marketKey ? marketByKey[marketKey] : null
    const col = market ? Q_COLORS[market.quadrant] : null
    return {
      fill: col ? col.fill : '#E2E8F0',
      stroke: col ? col.stroke : '#CBD5E1',
      strokeWidth: col ? 0.6 : 0.4,
      opacity: col ? 0.88 : 0.7,
    }
  }

  return (
    <div className="rounded-xl border border-slate-200 bg-white shadow-sm overflow-hidden">
      <div className="border-b border-slate-100 px-4 py-2.5 flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-[10px] font-semibold uppercase tracking-widest text-slate-400">Market Map — India</p>
          <p className="text-sm font-semibold text-slate-700">State-level investment priority · bubble size = category salience · label = YoY</p>
        </div>
        <div className="flex flex-wrap gap-3">
          {legendItems.map(([k, v]) => (
            <span key={k} className="flex items-center gap-1.5 text-[11px] font-semibold text-slate-600">
              <span className="inline-block h-3 w-3 rounded-sm" style={{ background: v.fill, border: `1.5px solid ${v.stroke}` }} />
              {v.legend}
            </span>
          ))}
        </div>
      </div>

      <div className="relative bg-[#EFF6FF]">
        {/* Stats panel — right-side empty space */}
        <div className="absolute right-3 top-3 flex flex-col gap-2 w-36">
          {/* National Elasticity */}
          {displayElasticity != null && (
            <div className="rounded-xl border border-blue-200 bg-white/90 px-3 py-2.5 shadow-sm backdrop-blur-sm">
              <p className="text-[9px] font-bold uppercase tracking-widest text-slate-400">All-India Elasticity</p>
              <p className="mt-1 text-xl font-black text-blue-700">{displayElasticity.toFixed(2)}</p>
              <p className="text-[9px] text-slate-500 leading-tight mt-0.5">Media responsiveness at national level</p>
            </div>
          )}
          {/* National YoY */}
          {displayYoy != null && (
            <div className="rounded-xl border border-slate-200 bg-white/90 px-3 py-2.5 shadow-sm backdrop-blur-sm">
              <p className="text-[9px] font-bold uppercase tracking-widest text-slate-400">Brand YoY Growth</p>
              <p className={`mt-1 text-xl font-black ${displayYoy >= 0 ? 'text-emerald-600' : 'text-red-500'}`}>
                {displayYoy >= 0 ? '+' : ''}{displayYoy.toFixed(1)}%
              </p>
              <p className="text-[9px] text-slate-500 leading-tight mt-0.5">Avg across {validYoys.length} markets</p>
            </div>
          )}
          {/* Quadrant split */}
          <div className="rounded-xl border border-slate-200 bg-white/90 px-3 py-2.5 shadow-sm backdrop-blur-sm">
            <p className="text-[9px] font-bold uppercase tracking-widest text-slate-400 mb-1.5">Market Split</p>
            {([
              ['increase', '#41C185', '↑ Increase'],
              ['maintain_salience', '#FFBD59', '— Hold'],
              ['maintain_elasticity', '#458EE2', '◎ Selective'],
              ['scale_back', '#F87171', '↓ Scale Back'],
            ] as const).map(([key, color, label]) => quadrantCounts[key] > 0 ? (
              <div key={key} className="flex items-center justify-between mb-1">
                <span className="flex items-center gap-1 text-[9px] text-slate-600 font-semibold">
                  <span className="h-2 w-2 rounded-sm inline-block flex-shrink-0" style={{ background: color }} />
                  {label}
                </span>
                <span className="text-[10px] font-black text-slate-700">{quadrantCounts[key]}</span>
              </div>
            ) : null)}
          </div>
        </div>

        <ComposableMap
          projection="geoMercator"
          projectionConfig={{ center: [82, 23], scale: 700 }}
          width={800}
          height={440}
          style={{ width: '100%', height: 'auto', display: 'block' }}
        >
          <Geographies geography={INDIA_GEO}>
            {({ geographies }: { geographies: Array<{ rsmKey: string; properties: Record<string, string> }> }) =>
              geographies.map((geo) => {
                const s = getStyle(geo.properties)
                const stateName = geo.properties.ST_NM || ''
                const marketKey = STATE_TO_MARKET[stateName]
                const market = marketKey ? marketByKey[marketKey] : null
                return (
                  <Geography
                    key={geo.rsmKey}
                    geography={geo}
                    fill={s.fill}
                    stroke={s.stroke}
                    strokeWidth={s.strokeWidth}
                    onClick={() => {
                      if (market && onMarketClick) onMarketClick(market)
                    }}
                    style={{
                      default: { outline: 'none', opacity: s.opacity },
                      hover:   { outline: 'none', opacity: 1, filter: 'brightness(1.07)', cursor: market && onMarketClick ? 'pointer' : 'default' },
                      pressed: { outline: 'none' },
                    }}
                  />
                )
              })
            }
          </Geographies>

          {markets.map((m) => {
            const pos = CENTROIDS[m.market]
            if (!pos) return null
            const name = DISPLAY[m.market] ?? m.market
            const yoy = m.yoy_pct
            const col = Q_COLORS[m.quadrant]
            const r = 5 + (m.category_salience / salMax) * 10

            return (
              <Marker key={m.market} coordinates={pos} onClick={() => onMarketClick?.(m)} style={{ cursor: onMarketClick ? 'pointer' : 'default' }}>
                <circle r={r} fill={col?.fill ?? '#94A3B8'} stroke="white" strokeWidth={1.5} opacity={0.95} />
                <text
                  textAnchor="middle"
                  y={-r - 4}
                  style={{ fontSize: 7.5, fontWeight: 800, fill: col?.stroke ?? '#334155', fontFamily: 'Inter, sans-serif' }}
                >
                  {name}
                </text>
                {yoy != null && (
                  <text
                    textAnchor="middle"
                    y={r + 11}
                    style={{ fontSize: 6.5, fontWeight: 700, fill: yoy >= 0 ? '#15803d' : '#dc2626', fontFamily: 'Inter, sans-serif' }}
                  >
                    {yoy >= 0 ? '+' : ''}{yoy}%
                  </text>
                )}
              </Marker>
            )
          })}
        </ComposableMap>
      </div>
    </div>
  )
}
