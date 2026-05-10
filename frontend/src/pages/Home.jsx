import { Link } from 'react-router-dom'

export default function Home() {
  const features = [
    {
      icon: '🎯',
      title: 'Default Risk Scoring',
      desc: 'XGBoost model trained on 200,000+ real loans predicts Probability of Default with AUC of 0.71'
    },
    {
      icon: '💰',
      title: 'Fair Value Estimation',
      desc: 'DCF pricing engine computes risk-adjusted fair value using live market rates from FRED'
    },
    {
      icon: '⚡',
      title: 'Investment Decisions',
      desc: 'Risk-Adjusted Yield (RAY) analysis delivers BUY / HOLD / AVOID signals benchmarked to live treasuries'
    },
    {
      icon: '🌪️',
      title: 'Stress Testing',
      desc: 'Recession scenario modelling shows NAV impact under Mild (-4.5%) and Severe (-11.2%) downturns'
    },
  ]

  return (
    <div style={{ maxWidth: 960, margin: '0 auto', padding: '60px 24px' }}>

      {/* Hero */}
      <div style={{ textAlign: 'center', marginBottom: 64 }}>
        <div style={{
          display: 'inline-block',
          background: '#1e2438',
          border: '1px solid #3b82f6',
          borderRadius: 999,
          padding: '4px 16px',
          fontSize: 12,
          color: '#3b82f6',
          fontWeight: 600,
          marginBottom: 20,
          letterSpacing: '0.05em',
        }}>
          PORTFOLIO VALUATION · CREDIT RISK · FAIR VALUE
        </div>
        <h1 style={{
          fontSize: 48,
          fontWeight: 800,
          lineHeight: 1.15,
          marginBottom: 20,
          background: 'linear-gradient(135deg, #e2e8f0, #3b82f6)',
          WebkitBackgroundClip: 'text',
          WebkitTextFillColor: 'transparent',
        }}>
          Private Credit Risk &<br />Fair Value Estimator
        </h1>
        <p style={{
          fontSize: 18,
          color: '#718096',
          maxWidth: 560,
          margin: '0 auto 32px',
          lineHeight: 1.6,
        }}>
          End-to-end quantitative pipeline that automates the Portfolio
          Valuation workflows performed by alternative asset managers
          every quarter.
        </p>
        <div style={{ display: 'flex', gap: 12, justifyContent: 'center' }}>
          <Link to="/score" className="btn btn-primary">
            Score a Loan →
          </Link>
          <Link to="/portfolio" className="btn"
            style={{ background: '#1a1f2e', border: '1px solid #2d3748', color: '#e2e8f0' }}>
            Upload Portfolio
          </Link>
        </div>
      </div>

      {/* Features */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
        gap: 16,
        marginBottom: 64,
      }}>
        {features.map(f => (
          <div key={f.title} className="card">
            <div style={{ fontSize: 28, marginBottom: 12 }}>{f.icon}</div>
            <h3 style={{ fontSize: 15, fontWeight: 700, marginBottom: 8 }}>
              {f.title}
            </h3>
            <p style={{ fontSize: 13, color: '#718096', lineHeight: 1.6 }}>
              {f.desc}
            </p>
          </div>
        ))}
      </div>

      {/* Stats */}
      <div className="card">
        <h2 style={{ fontSize: 18, fontWeight: 700, marginBottom: 20 }}>
          Model Results
        </h2>
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))',
          gap: 24,
        }}>
          {[
            { label: 'Loans Trained On',    value: '200,000+' },
            { label: 'Model AUC-ROC',        value: '0.7055' },
            { label: 'Recall',               value: '67.5%' },
            { label: 'Portfolio Par',        value: '$602M' },
            { label: 'Severe Recession Hit', value: '-11.2%' },
            { label: 'Data Warehouse',       value: 'Snowflake' },
          ].map(s => (
            <div key={s.label}>
              <div style={{
                fontSize: 24,
                fontWeight: 800,
                color: '#3b82f6',
                marginBottom: 4,
              }}>
                {s.value}
              </div>
              <div style={{ fontSize: 12, color: '#718096' }}>
                {s.label}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}