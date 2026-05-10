import { useState } from 'react'
import { api } from '../api'
import VerdictBadge from '../components/VerdictBadge'
import {
  RadarChart, Radar, PolarGrid,
  PolarAngleAxis, ResponsiveContainer, Tooltip
} from 'recharts'

const FIELD = ({ label, children }) => (
  <div>
    <label>{label}</label>
    {children}
  </div>
)

export default function LoanScorer() {
  const [form, setForm] = useState({
    loan_amnt: 15000, int_rate: 12.5, grade: 'B',
    annual_inc: 65000, dti: 18.5, fico_score: 710,
    home_ownership: 'RENT', purpose: 'debt_consolidation',
    term_months: 36, delinq_2yrs: 0,
  })
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError]   = useState(null)

  const set = (k, v) => setForm(f => ({ ...f, [k]: v }))

  const submit = async () => {
    setLoading(true)
    setError(null)
    try {
      const r = await api.scoreLoan({
        ...form,
        loan_amnt:   parseFloat(form.loan_amnt),
        int_rate:    parseFloat(form.int_rate),
        annual_inc:  parseFloat(form.annual_inc),
        dti:         parseFloat(form.dti),
        fico_score:  parseFloat(form.fico_score),
        term_months: parseInt(form.term_months),
        delinq_2yrs: parseInt(form.delinq_2yrs),
      })
      setResult(r)
    } catch (e) {
      setError(e.response?.data?.detail || 'API error')
    }
    setLoading(false)
  }

  const radarData = result ? [
    { metric: 'PD Risk',    value: Math.round(result.risk_metrics.pd_pct) },
    { metric: 'LGD',        value: Math.round(result.risk_metrics.lgd_pct) },
    { metric: 'DTI',        value: Math.min(Math.round(form.dti), 100) },
    { metric: 'FV Premium', value: Math.min(Math.round(result.risk_metrics.fair_value_pct), 100) },
    { metric: 'RAY Score',  value: Math.max(0, Math.min(Math.round(result.investment.ray + 20), 100)) },
  ] : []

  return (
    <div style={{ maxWidth: 960, margin: '0 auto', padding: '40px 24px' }}>
      <h1 style={{ fontSize: 28, fontWeight: 800, marginBottom: 8 }}>
        Loan Scorer
      </h1>
      <p style={{ color: '#718096', marginBottom: 32 }}>
        Enter loan details to get a full credit risk report and
        investment recommendation.
      </p>

      {/* Form */}
      <div className="card" style={{ marginBottom: 24 }}>
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
          gap: 16,
          marginBottom: 24,
        }}>
          <FIELD label="Loan Amount ($)">
            <input type="number" value={form.loan_amnt}
              onChange={e => set('loan_amnt', e.target.value)} />
          </FIELD>
          <FIELD label="Interest Rate (%)">
            <input type="number" step="0.1" value={form.int_rate}
              onChange={e => set('int_rate', e.target.value)} />
          </FIELD>
          <FIELD label="Grade">
            <select value={form.grade}
              onChange={e => set('grade', e.target.value)}>
              {['A','B','C','D','E','F','G'].map(g => (
                <option key={g}>{g}</option>
              ))}
            </select>
          </FIELD>
          <FIELD label="Annual Income ($)">
            <input type="number" value={form.annual_inc}
              onChange={e => set('annual_inc', e.target.value)} />
          </FIELD>
          <FIELD label="Debt-to-Income (%)">
            <input type="number" step="0.1" value={form.dti}
              onChange={e => set('dti', e.target.value)} />
          </FIELD>
          <FIELD label="FICO Score">
            <input type="number" value={form.fico_score}
              onChange={e => set('fico_score', e.target.value)} />
          </FIELD>
          <FIELD label="Home Ownership">
            <select value={form.home_ownership}
              onChange={e => set('home_ownership', e.target.value)}>
              {['RENT','OWN','MORTGAGE'].map(h => (
                <option key={h}>{h}</option>
              ))}
            </select>
          </FIELD>
          <FIELD label="Purpose">
            <select value={form.purpose}
              onChange={e => set('purpose', e.target.value)}>
              {['debt_consolidation','credit_card','home_improvement',
                'other','major_purchase','small_business','car','medical'
              ].map(p => <option key={p}>{p}</option>)}
            </select>
          </FIELD>
          <FIELD label="Term (months)">
            <select value={form.term_months}
              onChange={e => set('term_months', e.target.value)}>
              <option value={36}>36</option>
              <option value={60}>60</option>
            </select>
          </FIELD>
          <FIELD label="Delinquencies (2yr)">
            <input type="number" min="0" max="10" value={form.delinq_2yrs}
              onChange={e => set('delinq_2yrs', e.target.value)} />
          </FIELD>
        </div>

        <button className="btn btn-primary" onClick={submit} disabled={loading}>
          {loading ? 'Analysing...' : 'Analyse Loan →'}
        </button>
        {error && (
          <p style={{ color: '#ef4444', marginTop: 12, fontSize: 14 }}>
            {error}
          </p>
        )}
      </div>

      {/* Results */}
      {result && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>

          {/* Verdict */}
          <VerdictBadge
            verdict={result.investment.verdict}
            confidence={result.investment.confidence}
            reason={result.investment.reason}
          />

          {/* Metrics grid */}
          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))',
            gap: 12,
          }}>
            {[
              { label: 'Probability of Default', value: `${result.risk_metrics.pd_pct}%`,
                color: result.risk_metrics.pd_pct > 30 ? '#ef4444' : '#10b981' },
              { label: 'Loss Given Default',      value: `${result.risk_metrics.lgd_pct}%`,
                color: '#f59e0b' },
              { label: 'Expected Loss',           value: `$${result.risk_metrics.expected_loss.toLocaleString()}`,
                color: '#ef4444' },
              { label: 'Fair Value',              value: `$${result.risk_metrics.fair_value.toLocaleString()}`,
                color: '#3b82f6' },
              { label: 'Fair Value %',            value: `${result.risk_metrics.fair_value_pct}%`,
                color: '#3b82f6' },
              { label: 'Risk-Adjusted Yield',     value: `${result.investment.ray}%`,
                color: result.investment.ray > 0 ? '#10b981' : '#ef4444' },
              { label: 'Excess Spread',           value: `${result.investment.excess_spread}%`,
                color: result.investment.excess_spread > 0 ? '#10b981' : '#ef4444' },
              { label: '10Y Treasury',            value: `${result.market.treasury_10y}%`,
                color: '#718096' },
            ].map(m => (
              <div key={m.label} className="card"
                style={{ padding: 16, textAlign: 'center' }}>
                <div style={{
                  fontSize: 22, fontWeight: 800,
                  color: m.color, marginBottom: 4
                }}>
                  {m.value}
                </div>
                <div style={{ fontSize: 11, color: '#718096' }}>
                  {m.label}
                </div>
              </div>
            ))}
          </div>

          {/* Radar chart */}
          <div className="card">
            <h3 style={{ fontSize: 15, fontWeight: 700, marginBottom: 16 }}>
              Risk Profile
            </h3>
            <ResponsiveContainer width="100%" height={280}>
              <RadarChart data={radarData}>
                <PolarGrid stroke="#2d3748" />
                <PolarAngleAxis
                  dataKey="metric"
                  tick={{ fill: '#718096', fontSize: 12 }}
                />
                <Radar
                  dataKey="value"
                  stroke="#3b82f6"
                  fill="#3b82f6"
                  fillOpacity={0.25}
                />
                <Tooltip
                  contentStyle={{
                    background: '#1a1f2e',
                    border: '1px solid #2d3748',
                    borderRadius: 8,
                    color: '#e2e8f0',
                  }}
                />
              </RadarChart>
            </ResponsiveContainer>
          </div>

        </div>
      )}
    </div>
  )
}