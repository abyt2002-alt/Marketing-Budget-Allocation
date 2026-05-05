import { ComposableMap, Geographies, Geography, Marker } from 'react-simple-maps'
import type { FrameworkMarket } from './InvestmentFrameworkChart'

interface Props {
  markets: FrameworkMarket[]
  onMarketClick?: (market: FrameworkMarket) => void
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

export function IndiaMapChart({ markets, onMarketClick }: Props) {
  const marketByKey = Object.fromEntries(markets.map((m) => [m.market, m]))
  const salMax = Math.max(...markets.map((m) => m.brand_salience), 0.001)
  const legendItems = (Object.entries(Q_COLORS) as [string, typeof Q_COLORS[string]][])
    .filter(([k]) => markets.some((m) => m.quadrant === k))

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
      <div className="border-b border-slate-100 px-5 py-3 flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-[10px] font-semibold uppercase tracking-widest text-slate-400">Market Map — India</p>
          <p className="text-sm font-semibold text-slate-700">State-level investment priority · bubble size = brand salience · label = YoY</p>
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

      <div className="bg-[#EFF6FF]">
        <ComposableMap
          projection="geoMercator"
          projectionConfig={{ center: [82, 23], scale: 1150 }}
          width={800}
          height={680}
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
            const r = 5 + (m.brand_salience / salMax) * 10

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
