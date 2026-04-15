/**
 * StatusPareto — Horizontal bar chart showing accumulated status distribution.
 * Also serves as a color legend for the StatusTimeline below.
 */

import { colors, typography, statusColors, getStatusLabel, getStatusColor } from '../styles/theme'

export default function StatusPareto({ statusData = [] }) {
  // statusData: [{ word_status: 18, duration_min: 400 }, { word_status: 32, duration_min: 50 }, ...]
  // Sort by duration descending
  const sorted = [...statusData].sort((a, b) => b.duration_min - a.duration_min)
  const totalMin = sorted.reduce((sum, s) => sum + s.duration_min, 0) || 1

  return (
    <div>
      <p style={{ ...typography.titleSmall, color: colors.onSurface, marginBottom: 12 }}>
        Accumulated Status
      </p>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        {sorted.map((s) => {
          const pct = (s.duration_min / totalMin) * 100
          const color = getStatusColor(s.word_status)
          const label = getStatusLabel(s.word_status)

          return (
            <div key={s.word_status}>
              {/* Label row */}
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 3 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  <div style={{ width: 10, height: 10, borderRadius: 2, background: color, flexShrink: 0 }} />
                  <span style={{ ...typography.labelSmall, color: colors.onSurface }}>
                    {label}
                  </span>
                </div>
                <span style={{ ...typography.labelSmall, color: colors.onSurfaceVariant }}>
                  {pct.toFixed(1)}%
                </span>
              </div>
              {/* Bar */}
              <div style={{
                height: 16, borderRadius: 3, background: colors.surfaceVariant, overflow: 'hidden',
              }}>
                <div style={{
                  height: '100%',
                  width: `${pct}%`,
                  background: color,
                  borderRadius: 3,
                  transition: 'width 0.6s ease',
                  minWidth: pct > 0 ? 4 : 0,
                }} />
              </div>
            </div>
          )
        })}
      </div>

      {sorted.length === 0 && (
        <p style={{ ...typography.bodySmall, color: colors.outlineVariant, textAlign: 'center', padding: 16 }}>
          Sem dados de status
        </p>
      )}
    </div>
  )
}
