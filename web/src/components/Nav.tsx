import { NavLink } from 'react-router-dom'
import { useAuth } from '@/lib/auth'

const LINKS = [
  { to: '/', label: 'Today', end: true },
  { to: '/log', label: 'Log', end: false },
  { to: '/sources', label: 'Sources', end: false },
]

/**
 * Minimal top nav. Current page reads by weight, not color — --clay is
 * reserved for tonight's prescription and the primary action, never
 * wayfinding.
 */
export function Nav() {
  const { signOut } = useAuth()

  return (
    <nav
      style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        padding: `var(--space-3) var(--screen-pad-x)`,
        borderBottom: '1px solid var(--rule)',
      }}
    >
      <ul style={{ display: 'flex', gap: 'var(--space-5)' }}>
        {LINKS.map((link) => (
          <li key={link.to}>
            <NavLink
              to={link.to}
              end={link.end}
              style={({ isActive }) => ({
                fontFamily: 'var(--font-text)',
                fontSize: '15px',
                fontWeight: isActive ? 500 : 400,
                color: isActive ? 'var(--ink)' : 'var(--ink-faint)',
                textDecoration: 'none',
              })}
            >
              {link.label}
            </NavLink>
          </li>
        ))}
      </ul>
      <button
        onClick={() => void signOut()}
        style={{
          background: 'none',
          border: 'none',
          padding: 0,
          font: 'inherit',
          fontSize: '13px',
          color: 'var(--ink-faint)',
          cursor: 'pointer',
        }}
      >
        Sign out
      </button>
    </nav>
  )
}
