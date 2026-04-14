/**
 * Login — Tela de autenticação ME2.
 */

import { useState } from 'react'
import { colors, typography, shape } from '../styles/theme'
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
        // Fetch user profile
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
    <div
      style={{
        display: 'flex',
        justifyContent: 'center',
        alignItems: 'center',
        minHeight: '100vh',
        background: colors.background,
      }}
    >
      <form
        onSubmit={handleSubmit}
        style={{
          background: '#FFFFFF',
          padding: '40px',
          borderRadius: shape.extraLarge,
          width: '100%',
          maxWidth: '400px',
          boxShadow: '0 4px 12px rgba(0,0,0,0.1)',
        }}
      >
        {/* Logo */}
        <div style={{ textAlign: 'center', marginBottom: '32px' }}>
          <h1 style={{ ...typography.displaySmall, color: colors.primary, fontWeight: 700 }}>
            ME2
          </h1>
          <p style={{ ...typography.bodyMedium, color: colors.onSurfaceVariant }}>
            Keep Moving
          </p>
        </div>

        {/* Error */}
        {error && (
          <div
            style={{
              background: colors.errorContainer,
              color: colors.error,
              padding: '8px 16px',
              borderRadius: shape.small,
              marginBottom: '16px',
              ...typography.bodySmall,
            }}
          >
            {error}
          </div>
        )}

        {/* Email */}
        <div style={{ marginBottom: '16px' }}>
          <label style={{ ...typography.labelMedium, color: colors.onSurfaceVariant, display: 'block', marginBottom: '4px' }}>
            Email
          </label>
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
            style={{
              width: '100%',
              padding: '12px 16px',
              borderRadius: shape.small,
              border: `1px solid ${colors.outlineVariant}`,
              ...typography.bodyLarge,
              outline: 'none',
            }}
          />
        </div>

        {/* Password */}
        <div style={{ marginBottom: '24px' }}>
          <label style={{ ...typography.labelMedium, color: colors.onSurfaceVariant, display: 'block', marginBottom: '4px' }}>
            Senha
          </label>
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            style={{
              width: '100%',
              padding: '12px 16px',
              borderRadius: shape.small,
              border: `1px solid ${colors.outlineVariant}`,
              ...typography.bodyLarge,
              outline: 'none',
            }}
          />
        </div>

        <Button
          variant="filled"
          disabled={loading}
          style={{ width: '100%', justifyContent: 'center' }}
        >
          {loading ? 'Entrando...' : 'Entrar'}
        </Button>

        <p style={{ ...typography.bodySmall, color: colors.onSurfaceVariant, textAlign: 'center', marginTop: '24px' }}>
          Meitech Industrial &copy; {new Date().getFullYear()}
        </p>
      </form>
    </div>
  )
}
