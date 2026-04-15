/**
 * Login — Tela de autenticação ME2 com identidade visual Meitech.
 */

import { useState } from 'react'
import { colors, typography, shape, elevation } from '../styles/theme'
import { useAuthStore } from '../lib/store'
import Button from '../components/Button'
import api from '../lib/api'

export default function Login() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(false)
  const setAuth = useAuthStore((s) => s.setAuth)

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError(null)
    setLoading(true)

    try {
      const res = await api.post('/api/v1/auth/login', { email, password })
      const { access_token } = res.data?.data ?? {}
      if (access_token) {
        const profileRes = await api.get('/api/v1/auth/me', {
          headers: { Authorization: `Bearer ${access_token}` },
        })
        setAuth(access_token, profileRes.data?.data ?? null)
      }
    } catch (err) {
      setError(err.response?.data?.detail ?? 'Erro ao fazer login')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{
      display: 'flex', justifyContent: 'center', alignItems: 'center',
      minHeight: '100vh', background: colors.background,
    }}>
      <form
        onSubmit={handleSubmit}
        style={{
          background: '#FFFFFF',
          padding: '48px 40px',
          borderRadius: shape.extraLarge,
          width: '100%',
          maxWidth: '400px',
          boxShadow: elevation.level3,
        }}
      >
        {/* Meitech Logo */}
        <div style={{ textAlign: 'center', marginBottom: 32 }}>
          <div style={{
            width: 72, height: 72, borderRadius: '50%',
            background: colors.meitech,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            margin: '0 auto 16px',
          }}>
            <img
              src="/brand/logo-white.svg"
              alt="Meitech"
              style={{ width: 48, height: 'auto' }}
            />
          </div>

          <h1 style={{
            fontFamily: typography.brandFamily,
            fontSize: 32, fontWeight: 700,
            color: colors.meitech,
            letterSpacing: '-0.5px',
            lineHeight: 1,
          }}>
            ME2
          </h1>
          <p style={{
            fontFamily: typography.brandFamily,
            fontSize: 11, fontWeight: 400,
            color: colors.outline,
            letterSpacing: '3px',
            textTransform: 'uppercase',
            marginTop: 4,
          }}>
            Keep Moving
          </p>
        </div>

        {/* Error */}
        {error && (
          <div style={{
            background: colors.errorContainer,
            color: colors.error,
            padding: '10px 16px',
            borderRadius: shape.small,
            marginBottom: 16,
            ...typography.bodySmall,
          }}>
            {error}
          </div>
        )}

        {/* Email */}
        <div style={{ marginBottom: 16 }}>
          <label style={{ ...typography.labelMedium, color: colors.onSurfaceVariant, display: 'block', marginBottom: 6 }}>
            Email
          </label>
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
            placeholder="seu.email@meitech.com.br"
            style={{
              width: '100%', padding: '12px 16px',
              borderRadius: shape.small,
              border: `1px solid ${colors.outlineVariant}`,
              ...typography.bodyMedium, outline: 'none',
              transition: 'border-color 0.2s',
            }}
            onFocus={(e) => e.target.style.borderColor = colors.meitech}
            onBlur={(e) => e.target.style.borderColor = colors.outlineVariant}
          />
        </div>

        {/* Password */}
        <div style={{ marginBottom: 28 }}>
          <label style={{ ...typography.labelMedium, color: colors.onSurfaceVariant, display: 'block', marginBottom: 6 }}>
            Senha
          </label>
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            style={{
              width: '100%', padding: '12px 16px',
              borderRadius: shape.small,
              border: `1px solid ${colors.outlineVariant}`,
              ...typography.bodyMedium, outline: 'none',
              transition: 'border-color 0.2s',
            }}
            onFocus={(e) => e.target.style.borderColor = colors.meitech}
            onBlur={(e) => e.target.style.borderColor = colors.outlineVariant}
          />
        </div>

        {/* Submit */}
        <Button
          variant="filled"
          disabled={loading}
          style={{
            width: '100%', justifyContent: 'center',
            background: colors.meitech, padding: '12px 24px',
          }}
        >
          {loading ? 'Entrando...' : 'Entrar'}
        </Button>

        {/* Footer */}
        <p style={{
          ...typography.bodySmall, color: colors.outlineVariant,
          textAlign: 'center', marginTop: 32,
        }}>
          <span style={{ fontFamily: typography.brandFamily, fontWeight: 700, color: colors.outline }}>
            Meitech Industrial
          </span>
          {' '}&copy; {new Date().getFullYear()}
        </p>
      </form>
    </div>
  )
}
