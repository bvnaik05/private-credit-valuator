import { Link, useLocation } from 'react-router-dom'

export default function Navbar() {
  const { pathname } = useLocation()

  const links = [
    { to: '/',          label: 'Home' },
    { to: '/score',     label: 'Loan Scorer' },
    { to: '/portfolio', label: 'Portfolio' },
  ]

  return (
    <nav style={{
      background: '#1a1f2e',
      borderBottom: '1px solid #2d3748',
      padding: '0 32px',
      display: 'flex',
      alignItems: 'center',
      height: 60,
      gap: 32,
    }}>
      <span style={{
        fontWeight: 800,
        fontSize: 16,
        color: '#3b82f6',
        letterSpacing: '-0.02em'
      }}>
        CreditLens
      </span>
      <div style={{ display: 'flex', gap: 8 }}>
        {links.map(link => (
          <Link
            key={link.to}
            to={link.to}
            style={{
              padding: '6px 16px',
              borderRadius: 8,
              fontSize: 14,
              fontWeight: 500,
              textDecoration: 'none',
              color: pathname === link.to ? 'white' : '#718096',
              background: pathname === link.to ? '#2d3748' : 'transparent',
              transition: 'all 0.15s',
            }}
          >
            {link.label}
          </Link>
        ))}
      </div>
    </nav>
  )
}