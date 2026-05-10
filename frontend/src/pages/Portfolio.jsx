import { useState } from 'react'
import { api } from '../api'
import VerdictBadge from '../components/VerdictBadge'
import {
  BarChart, Bar, XAxis, YAxis, Tooltip,
  ResponsiveContainer, Cell, PieChart, Pie, Legend
} from 'recharts'

const GRADE_COLORS = {
  A:'#10b981',B:'#3b82f6',C:'#8b5cf6',
  D:'#f59e0b',E:'#f97316',F:'#ef4444',G:'#7f1d1d'
}

export default function Portfolio() {
  const [result,  setResult]  = useState(null)
  const [loading, setLoading] = useState(false)
  const [error,   setError]   = useState(null)

  const upload = async (e) => {
    const file = e.target.files[0]
    if (!file) return
    setLoading(true)
    setError(null)
    try {
      const r = await api.analysePortfolio(file)
      setResult(r)
    } catch (err) {
      setError(err.response?.data?.detail || 'Upload failed')
    }
    setLoading(false)
  }

  const verdictData = result ? [
    { name: 'BUY',   value: result.summary.buy_count,   fill: '#10b981' },
    { name: 'HOLD',  value: result.summary.hold_count,  fill: '#f59e0b' },
    { name: 'AVOID', value: result.summary.avoid_count, fill: '#ef4444' },
  ] : []

  const overall = result
    ? result.summary.buy_pct >= 30  ? 'BUY'
    : result.summary.avoid_pct >= 70 ? 'AVOID'
    : 'HOLD'
    : null

  return (
    <div style={{ maxWidth: 960, margin: '0 auto', padding: '40px 24px' }}>
      <h1 style={{ fontSize: 28, fontWeight: 800, marginBottom: 8 }}>
        Portfolio Analyser
      </h1>
      <p style={{ color: '#718096', marginBottom: 32 }}>
        Upload a CSV of loans to get full portfolio risk analytics,
        fair value, and investment breakdown.
      </p>

      {/* Upload */}
      <div className="card" style={{ marginBottom: 24 }}>
        <p style={{ fontSize: 13, color: '#718096', marginBottom: 16 }}>
          CSV must include: <code style={{ color: '#3b82f6' }}>
            loan_amnt, int_rate, grade, annual_inc, dti,
            fico_score, home_ownership
          </code>
        </p>
        <input type="file" accept=".csv" onChange={upload}
          style={{ width: 'auto', cursor: 'pointer' }} />
        {loading && (
          <p style={{ color: '#3b82f6', marginTop: 12 }}>
            Analysing portfolio...
          </p>
        )}
        {error && (
          <p style={{ color: '#ef4444', marginTop: 12 }}>{error}</p>
        )}
      </div>

      {result && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>

          {/* Overall verdict */}
          <VerdictBadge
            verdict={overall}
            confidence="Medium"
            reason={`${result.summary.buy_pct}% BUY · ${result.summary.avoid_pct}% AVOID · ${result.summary.total_loans} loans analysed`}
          />

          {/* KPI row */}
          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))',
            gap: 12,
          }}>
            {[
              { label: 'Total Loans',    value: result.summary.total_loans.toLocaleString() },
              { label: 'Total Par',      value: `$${(result.summary.total_par/1e6).toFixed(1)}M` },
              { label: 'Total FV',       value: `$${(result.summary.total_fv/1e6).toFixed(1)}M` },
              { label: 'Expected Loss',  value: `$${(result.summary.total_el/1e6).toFixed(1)}M` },
              { label: 'Avg PD',         value: `${(result.summary.avg_pd*100).toFixed(1)}%` },
              { label: 'Avg RAY',        value: `${result.summary.avg_ray.toFixed(2)}%` },
            ].map(m => (
              <div key={m.label} className="card" style={{ padding: 16, textAlign: 'center' }}>
                <div style={{ fontSize: 22, fontWeight: 800, color: '#3b82f6', marginBottom: 4 }}>
                  {m.value}
                </div>
                <div style={{ fontSize: 11, color: '#718096' }}>{m.label}</div>
              </div>
            ))}
          </div>

          {/* Charts row */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>

            {/* Verdict pie */}
            <div className="card">
              <h3 style={{ fontSize: 15, fontWeight: 700, marginBottom: 16 }}>
                Verdict Breakdown
              </h3>
              <ResponsiveContainer width="100%" height={220}>
                <PieChart>
                  <Pie data={verdictData} dataKey="value"
                    nameKey="name" cx="50%" cy="50%" outerRadius={80} label>
                    {verdictData.map((d, i) => (
                      <Cell key={i} fill={d.fill} />
                    ))}
                  </Pie>
                  <Legend />
                  <Tooltip
                    contentStyle={{
                      background: '#1a1f2e',
                      border: '1px solid #2d3748',
                      borderRadius: 8,
                      color: '#e2e8f0',
                    }}
                  />
                </PieChart>
              </ResponsiveContainer>
            </div>

            {/* Grade bar */}
            <div className="card">
              <h3 style={{ fontSize: 15, fontWeight: 700, marginBottom: 16 }}>
                Avg PD by Grade
              </h3>
              <ResponsiveContainer width="100%" height={220}>
                <BarChart data={result.grade_breakdown}>
                  <XAxis dataKey="grade"
                    tick={{ fill: '#718096', fontSize: 12 }} />
                  <YAxis tickFormatter={v => `${(v*100).toFixed(0)}%`}
                    tick={{ fill: '#718096', fontSize: 11 }} />
                  <Tooltip
                    formatter={v => `${(v*100).toFixed(1)}%`}
                    contentStyle={{
                      background: '#1a1f2e',
                      border: '1px solid #2d3748',
                      borderRadius: 8,
                      color: '#e2e8f0',
                    }}
                  />
                  <Bar dataKey="avg_pd" radius={[4,4,0,0]}>
                    {result.grade_breakdown.map((d, i) => (
                      <Cell key={i}
                        fill={GRADE_COLORS[d.grade] || '#3b82f6'} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>

        </div>
      )}
    </div>
  )
}