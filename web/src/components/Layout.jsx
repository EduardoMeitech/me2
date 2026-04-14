/**
 * Layout — Nav Rail (desktop) + Bottom Nav (mobile) + content area.
 */

import { useLocation, useNavigate } from 'react-router-dom'
import { colors, typography, shape, elevation } from '../styles/theme'
import { useAuthStore } from '../lib/store'

const navItems = [
  { path: '/', label: 'Monitor', icon: '&#9881;' },
  { path: '/oee', label: 'OEE', icon: '&#9733;' },
  { path: '/alerts', label: 'Alertas', icon: '&#9888;' },
  { path: '/reports', label: 'Relatórios', icon: '&#128196;' },
]

export default function Layout({ children }) {
  const location = useLocation()
  const navigate = useNavigate()
  const user = useAuthStore((s) => s.user)
  const logout = useAuthStore((s) => s.logout)

  return (
    <div style={{ display: 'flex', minHeight: '100vh' }}>
      {/* Side Nav Rail (desktop) */}
      <nav
        style={{
          width: '80px',
          background: colors.surface,
          borderRight: `1px solid ${colors.outlineVariant}`,
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          paddingTop: '16px',
          gap: '4px',
        }}
      >
        {/* Logo */}
        <div
          style={{
            ...typography.titleLarge,
            color: colors.primary,
            fontWeight: 700,
            marginBottom: '24px',
            cursor: 'pointer',
          }}
          onClick={() => navigate('/')}
        >
          ME2
        </div>

        {navItems.map((item) => {
          const isActive = location.pathname === item.path

          return (
            <button
              key={item.path}
              onClick={() => navigate(item.path)}
              style={{
                width: '56px',
                height: '56px',
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                justifyContent: 'center',
                gap: '2px',
                border: 'none',
                borderRadius: shape.large,
                background: isActive ? colors.primaryContainer : 'transparent',
                color: isActive ? colors.primary : colors.onSurfaceVariant,
                cursor: 'pointer',
                transition: 'background 0.2s',
              }}
            >
              <span style={{ fontSize: '18px' }} dangerouslySetInnerHTML={{ __html: item.icon }} />
              <span style={{ ...typography.labelSmall }}>{item.label}</span>
            </button>
          )
        })}

        {/* Spacer */}
        <div style={{ flex: 1 }} />

        {/* User / Logout */}
        <button
          onClick={logout}
          style={{
            width: '56px',
            height: '56px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            border: 'none',
            borderRadius: shape.large,
            background: 'transparent',
            color: colors.onSurfaceVariant,
            cursor: 'pointer',
            marginBottom: '16px',
            ...typography.labelSmall,
          }}
          title={user?.name ?? 'Sair'}
        >
          Sair
        </button>
      </nav>

      {/* Main content */}
      <main
        style={{
          flex: 1,
          padding: '24px',
          overflowY: 'auto',
          maxHeight: '100vh',
        }}
      >
        {children}
      </main>
    </div>
  )
}
