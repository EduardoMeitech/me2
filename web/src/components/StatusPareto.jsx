/**
 * StatusPareto — Horizontal bar chart showing accumulated status distribution.
 * Shows ALL known statuses (even 0%) to fill the card and serve as color legend.
 */

import { colors, typography, statusColors, getStatusLabel, getStatusColor } from '../styles/theme'

// All statuses to always display (in priority order)
const ALL_STATUSES = [18, 32, 20, 24, 64, 16, 128, 17]

export default function StatusPareto({ statusData = [] }) {
  const totalMin = statusData.reduce((sum, s) => sum + (s.duration_min ?? 0), 0) || 1

  // Build map from real data
  const dataMap = {}
  for (const s of statusData) {
    dataMap[s.word_status] = (dataMap[s.word_status] ?? 0) + (s.duration_min ?? 0)
  }

  // Merge with all known statuses, sort by duration desc
  const merged = ALL_STATUSES.map((ws) => ({
    word_status: ws,
    duration_min: dataMap[ws] ?? 0,
  })).sort((a, b) => b.duration_min - a.duration_min)

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <p style={{ ...typography.titleSmall, color: colors.onSurface, marginBottom: 12 }}>
        Accumulated Status
      </p>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6, flex: 1, justifyContent: 'space-evenly' }}>
        {merged.map((s) => {
          const pct = (s.duration_min / totalMin) * 100
          const color = getStatusColor(s.word_status)
          const label = getStatusLabel(s.word_status)

          return (
            <div key={s.word_status}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 2 }}>
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
              <div style={{
                height: 14, borderRadius: 3, background: colors.surfaceVariant, overflow: 'hidden',
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
    </div>
  )
}
