/**
 * Layout — Nav Rail (desktop) + Bottom Nav (mobile) + ME2 Footer
 * Meitech Visual Identity: blue rail, Amina font, SpinCircle animation
 */

import { useLocation, useNavigate } from 'react-router-dom'
import { colors, typography, shape, layout } from '../styles/theme'
import { useAuthStore } from '../lib/store'
import ME2Logo, { ME2LogoStatic } from './ME2Logo'

const RAIL_WIDTH = layout.railWidth

// ─── SpinCircle — Animated Meitech circle (SVG inline) ─────────────────────
function SpinCircle({ size = 40, speed = 7, reverse = false, color }) {
  const c = color || colors.meitech
  return (
    <div style={{ width: size, height: size, flexShrink: 0, animation: `meiSpin ${speed}s linear infinite${reverse ? ' reverse' : ''}` }}>
      <svg width="100%" height="100%" viewBox="0 0 197 197" fill="none">
        <path d="M141.685 161.266L154.813 179.342L157.988 177.032L144.859 158.956C143.816 159.746 142.773 160.521 141.685 161.266Z" fill={c} opacity="0.5"/>
        <path d="M151.014 153.711L166.809 169.507L169.507 166.809L153.711 151.014C152.832 151.938 151.938 152.832 151.014 153.711Z" fill={c} opacity="0.6"/>
        <path d="M131.299 167.286L141.432 187.18L145.023 185.347L134.89 165.453C133.713 166.094 132.52 166.705 131.299 167.286Z" fill={c} opacity="0.4"/>
        <path d="M174.692 98.5C174.692 99.051 174.692 99.603 174.677 100.139L197 100.139L197 96.846L174.662 96.846C174.662 97.397 174.677 97.934 174.677 98.485L174.692 98.5Z" fill={c} opacity="0.9"/>
        <path d="M173.485 112.09L195.525 115.577L196.061 112.224L174.007 108.737C173.858 109.855 173.679 110.987 173.485 112.09Z" fill={c} opacity="0.85"/>
        <path d="M108.32 174.066L111.807 196.121L115.995 195.45L112.508 173.396C111.122 173.649 109.721 173.873 108.32 174.051Z" fill={c} opacity="0.35"/>
        <path d="M159.03 144.77L177.106 157.898L179.282 154.903L161.221 141.774C160.521 142.788 159.79 143.786 159.03 144.77Z" fill={c} opacity="0.55"/>
        <path d="M170.415 123.714L191.635 130.613L192.723 127.29L171.503 120.39C171.175 121.508 170.803 122.626 170.43 123.714Z" fill={c} opacity="0.75"/>
        <path d="M165.558 134.696L185.436 144.829L187.076 141.625L167.197 131.492C166.675 132.58 166.124 133.653 165.558 134.696Z" fill={c} opacity="0.65"/>
        <path d="M120.078 171.593L126.977 192.827L130.911 191.546L124.012 170.311C122.715 170.773 121.404 171.19 120.078 171.593Z" fill={c} opacity="0.4"/>
        <path d="M98.5 174.692C97.77 174.692 97.054 174.692 96.324 174.662L96.324 197L100.676 197L100.676 174.662C99.96 174.677 99.23 174.692 98.5 174.692Z" fill={c} opacity="0.3"/>
        <path d="M173.992 88.158L196.046 84.671L195.554 81.527L173.515 85.014C173.694 86.057 173.858 87.1 174.007 88.158Z" fill={c} opacity="0.85"/>
        <path d="M45.242 44.034L29.461 28.254L28.268 29.446L44.049 45.227C44.452 44.824 44.839 44.422 45.242 44.034Z" fill={c} opacity="0.45"/>
        <path d="M64.763 30.191L54.63 10.312L52.931 11.176L63.064 31.055C63.63 30.757 64.196 30.474 64.763 30.191Z" fill={c} opacity="0.55"/>
        <path d="M75.909 25.72L69.025 4.515L67.102 5.141L73.987 26.346C74.628 26.137 75.254 25.929 75.909 25.72Z" fill={c} opacity="0.6"/>
        <path d="M37.344 53.08L19.298 39.966L18.359 41.248L36.405 54.361C36.718 53.929 37.031 53.497 37.344 53.08Z" fill={c} opacity="0.4"/>
        <path d="M87.637 23.098L84.15 1.058L82.049 1.386L85.536 23.425C86.236 23.306 86.936 23.202 87.637 23.098Z" fill={c} opacity="0.7"/>
        <path d="M98.5 22.323C98.873 22.323 99.245 22.323 99.618 22.323L99.618 0L97.397 0L97.397 22.323C97.77 22.323 98.142 22.323 98.515 22.323Z" fill={c} opacity="0.8"/>
        <path d="M153.338 45.614L169.119 29.833L167.167 27.881L151.386 43.662C152.042 44.303 152.698 44.943 153.338 45.614Z" fill={c} opacity="0.5"/>
        <path d="M171.429 76.416L192.649 69.516L191.695 66.595L170.475 73.495C170.818 74.463 171.131 75.432 171.429 76.416Z" fill={c} opacity="0.75"/>
        <path d="M123.207 26.421L130.092 5.216L127.767 4.456L120.882 25.661C121.657 25.899 122.432 26.152 123.207 26.421Z" fill={c} opacity="0.7"/>
        <path d="M144.352 37.656L157.466 19.595L155.32 18.031L142.207 36.092C142.937 36.598 143.652 37.12 144.352 37.656Z" fill={c} opacity="0.5"/>
        <path d="M111.569 23.44L115.056 1.401L112.746 1.043L109.259 23.083C110.034 23.187 110.794 23.306 111.569 23.44Z" fill={c} opacity="0.75"/>
        <path d="M134.219 31.204L144.352 11.325L142.087 10.163L131.954 30.042C132.714 30.414 133.474 30.802 134.219 31.204Z" fill={c} opacity="0.6"/>
        <path d="M160.968 54.883L179.029 41.769L177.345 39.46L159.284 52.588C159.865 53.348 160.416 54.123 160.968 54.898Z" fill={c} opacity="0.55"/>
        <path d="M167.063 65.239L186.941 55.106L185.6 52.469L165.721 62.602C166.183 63.466 166.645 64.36 167.077 65.239Z" fill={c} opacity="0.65"/>
      </svg>
    </div>
  )
}

// ─── ME2 Footer — "Keep Moving" with animated Meitech circles ──────────────
function ME2Footer() {
  return (
    <div style={{
      display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 20,
      padding: '32px 0 16px', opacity: 0.5,
    }}>
      <SpinCircle size={44} speed={7} reverse />
      <div style={{ textAlign: 'center' }}>
        <ME2LogoStatic size={15} />
        <div style={{
          fontFamily: typography.brandFamily, fontSize: 9, fontWeight: 400,
          color: colors.outline, letterSpacing: '2.5px', textTransform: 'uppercase',
        }}>
          Keep Moving
        </div>
      </div>
      <SpinCircle size={44} speed={10} />
    </div>
  )
}

// ─── Nav items ─────────────────────────────────────────────────────────────
const navItems = [
  { path: '/',        label: 'Monitor',     icon: '\u2699' },
  { path: '/oee',     label: 'OEE',         icon: '\u2605' },
  { path: '/alerts',  label: 'Alertas',     icon: '\u26A0' },
  { path: '/reports', label: 'Relatórios',  icon: '\uD83D\uDCC4' },
]

// ─── Main Layout ───────────────────────────────────────────────────────────
export default function Layout({ children }) {
  const location = useLocation()
  const navigate = useNavigate()
  const user = useAuthStore((s) => s.user)
  const logout = useAuthStore((s) => s.logout)

  return (
    <div style={{ display: 'flex', minHeight: '100vh' }}>
      {/* Nav Rail (desktop — hidden on mobile via CSS class) */}
      <nav
        className="me2-nav-rail"
        style={{
          width: RAIL_WIDTH,
          background: colors.meitech,
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          paddingTop: 16,
          gap: 4,
          position: 'fixed',
          top: 0,
          left: 0,
          bottom: 0,
          zIndex: 200,
        }}
      >
        {/* Meitech Logo + ME2 */}
        <div
          style={{ cursor: 'pointer', textAlign: 'center', marginBottom: 24 }}
          onClick={() => navigate('/')}
        >
          <img
            src="/brand/logo-white.svg"
            alt="Meitech"
            style={{ width: 64, height: 'auto', marginBottom: 2 }}
          />
          <ME2Logo size={34} light />
        </div>

        {/* Nav items */}
        {navItems.map((item) => {
          const isActive = location.pathname === item.path

          return (
            <button
              key={item.path}
              onClick={() => navigate(item.path)}
              style={{
                width: 64,
                padding: '8px 0',
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                justifyContent: 'center',
                gap: 2,
                border: 'none',
                borderRadius: shape.large,
                background: isActive ? 'rgba(255,255,255,0.22)' : 'transparent',
                color: '#fff',
                cursor: 'pointer',
                transition: 'background 0.2s',
                opacity: isActive ? 1 : 0.7,
              }}
            >
              <span style={{ fontSize: 20 }}>{item.icon}</span>
              <span style={{ fontSize: 10, fontWeight: 500, letterSpacing: '0.3px' }}>
                {item.label}
              </span>
            </button>
          )
        })}

        {/* Spacer */}
        <div style={{ flex: 1 }} />

        {/* User name */}
        {user && (
          <div style={{
            color: 'rgba(255,255,255,0.6)', fontSize: 9, textAlign: 'center',
            padding: '0 8px', wordBreak: 'break-word',
          }}>
            {user.name?.split(' ')[0]}
          </div>
        )}

        {/* Logout */}
        <button
          onClick={logout}
          style={{
            width: 56, height: 40,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            border: 'none', borderRadius: shape.large,
            background: 'transparent', color: 'rgba(255,255,255,0.6)',
            cursor: 'pointer', marginBottom: 16, fontSize: 10,
          }}
          title="Sair"
        >
          Sair
        </button>
      </nav>

      {/* Main content area */}
      <main
        className="me2-main-content"
        style={{
          flex: 1,
          marginLeft: RAIL_WIDTH,
          padding: 24,
          overflowY: 'auto',
          maxHeight: '100vh',
          display: 'flex',
          flexDirection: 'column',
        }}
      >
        {/* Content */}
        <div style={{ flex: 1 }}>
          {children}
        </div>

        {/* Footer */}
        <ME2Footer />
      </main>

      {/* Bottom Nav (mobile — hidden on desktop) */}
      <nav
        className="me2-bottom-nav"
        style={{
          display: 'none',
          position: 'fixed',
          bottom: 0,
          left: 0,
          right: 0,
          height: 64,
          background: colors.meitech,
          justifyContent: 'space-around',
          alignItems: 'center',
          zIndex: 200,
        }}
      >
        {navItems.map((item) => {
          const isActive = location.pathname === item.path

          return (
            <button
              key={item.path}
              onClick={() => navigate(item.path)}
              style={{
                flex: 1,
                padding: '8px 0',
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                gap: 2,
                border: 'none',
                borderRadius: shape.medium,
                background: isActive ? 'rgba(255,255,255,0.22)' : 'transparent',
                cursor: 'pointer',
                color: '#FFFFFF',
                opacity: isActive ? 1 : 0.7,
                transition: 'background 0.2s, opacity 0.2s',
              }}
            >
              <span style={{ fontSize: 20 }}>{item.icon}</span>
              <span style={{ fontSize: 10, fontWeight: 500, letterSpacing: '0.3px' }}>
                {item.label}
              </span>
            </button>
          )
        })}
      </nav>
    </div>
  )
}
