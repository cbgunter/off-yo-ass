import { NavLink } from 'react-router-dom'
import { useAuth } from '@/lib/auth'
import { StatusDot } from '@/components/StatusDot'

const LINKS = [
  { to: '/', label: 'Health', end: true },
  { to: '/call', label: 'Call', end: false },
  { to: '/eat', label: 'Eat', end: false },
]

/**
 * Bottom tab bar for the three screens, plus a small top-right cluster for
 * the two glance/rare controls (source status, sign out) that don't earn
 * a tab. Both respect the phone's safe areas so nothing rides under the
 * status bar or the gesture bar. Current page reads by weight, not colour
 * -- --clay is reserved for tonight's prescription and the primary
 * action, never wayfinding.
 */
export function Nav() {
  const { signOut } = useAuth()

  return (
    <>
      <div
        style={{
          position: 'fixed',
          top: 0,
          right: 0,
          zIndex: 1,
          display: 'flex',
          alignItems: 'center',
          gap: 'var(--space-4)',
          padding: `calc(var(--space-3) + env(safe-area-inset-top)) calc(var(--space-4) + env(safe-area-inset-right)) var(--space-3) var(--space-4)`,
          background: 'var(--paper)',
        }}
      >
        <StatusDot />
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
      </div>

      <nav
        style={{
          position: 'fixed',
          bottom: 0,
          left: 0,
          right: 0,
          zIndex: 1,
          borderTop: '1px solid var(--rule)',
          background: 'var(--paper)',
          paddingBottom: 'env(safe-area-inset-bottom)',
        }}
      >
        <ul
          style={{
            display: 'flex',
            justifyContent: 'space-around',
            alignItems: 'center',
            height: 'var(--nav-height)',
          }}
        >
          {LINKS.map((link) => (
            <li key={link.to}>
              <NavLink
                to={link.to}
                end={link.end}
                style={({ isActive }) => ({
                  display: 'block',
                  fontFamily: 'var(--font-text)',
                  fontSize: '15px',
                  fontWeight: isActive ? 500 : 400,
                  color: isActive ? 'var(--ink)' : 'var(--ink-faint)',
                  textDecoration: 'none',
                  padding: 'var(--space-2) var(--space-4)',
                })}
              >
                {link.label}
              </NavLink>
            </li>
          ))}
        </ul>
      </nav>
    </>
  )
}
