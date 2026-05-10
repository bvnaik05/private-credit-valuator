export default function VerdictBadge({ verdict, confidence, reason }) {
  const colors = {
    BUY:   { bg: '#064e3b', border: '#10b981', text: '#6ee7b7' },
    HOLD:  { bg: '#451a03', border: '#f59e0b', text: '#fcd34d' },
    AVOID: { bg: '#450a0a', border: '#ef4444', text: '#fca5a5' },
  }
  const c = colors[verdict] || colors.HOLD

  return (
    <div style={{
      background: c.bg,
      border: `2px solid ${c.border}`,
      borderRadius: 12,
      padding: '20px 24px',
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        <span style={{
          fontSize: 28,
          fontWeight: 800,
          color: c.text,
          letterSpacing: '0.05em'
        }}>
          {verdict === 'BUY'   ? '✅ BUY'   :
           verdict === 'HOLD'  ? '⚠️ HOLD'  : '🚫 AVOID'}
        </span>
        <span style={{
          background: c.border,
          color: 'white',
          fontSize: 11,
          fontWeight: 700,
          padding: '2px 10px',
          borderRadius: 999,
          textTransform: 'uppercase'
        }}>
          {confidence} confidence
        </span>
      </div>
      {reason && (
        <p style={{ marginTop: 8, color: c.text, opacity: 0.85, fontSize: 14 }}>
          {reason}
        </p>
      )}
    </div>
  )
}