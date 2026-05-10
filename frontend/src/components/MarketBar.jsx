import { useEffect, useState } from 'react'
import { api } from '../api'

export default function MarketBar() {
  const [market, setMarket] = useState(null)

  useEffect(() => {
    api.getMarket().then(setMarket).catch(() => {})
  }, [])

  if (!market) return null

  const items = [
    { label: '10Y Treasury', value: `${market.treasury_10y}%` },
    { label: 'Fed Funds',    value: `${market.fed_funds_rate}%` },
    { label: 'HY Spread',    value: `${market.hy_spread}%` },
    { label: 'HY Req Return',value: `${market.hy_required_return}%` },
  ]

  return (
    <div style={{
      background: '#1a1f2e',
      borderBottom: '1px solid #2d3748',
      padding: '8px 32px',
      display: 'flex',
      gap: 32,
      fontSize: 13,
      overflowX: 'auto',
    }}>
      <span style={{ color: '#718096', fontWeight: 600 }}>
        LIVE MARKET
      </span>
      {items.map(item => (
        <div key={item.label} style={{ display: 'flex', gap: 8 }}>
          <span style={{ color: '#718096' }}>{item.label}</span>
          <span style={{ color: '#3b82f6', fontWeight: 700 }}>
            {item.value}
          </span>
        </div>
      ))}
    </div>
  )
}