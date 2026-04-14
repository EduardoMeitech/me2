/**
 * OEEGauge — Gauge circular MD3 com 3 arcos (Disponibilidade, Performance, Qualidade).
 */

import { colors, typography } from '../styles/theme'

const SIZE = 200
const STROKE = 14
const RADIUS = (SIZE - STROKE) / 2
const CIRCUMFERENCE = 2 * Math.PI * RADIUS

function Arc({ value, color, offset, radius }) {
  const r = radius
  const circ = 2 * Math.PI * r
  const dashArray = `${circ * value} ${circ * (1 - value)}`

  return (
    <circle
      cx={SIZE / 2}
      cy={SIZE / 2}
      r={r}
      fill="none"
      stroke={color}
      strokeWidth={STROKE}
      strokeDasharray={dashArray}
      strokeDashoffset={offset}
      strokeLinecap="round"
      transform={`rotate(-90 ${SIZE / 2} ${SIZE / 2})`}
      style={{ transition: 'stroke-dasharray 0.8s ease' }}
    />
  )
}

export default function OEEGauge({ availability = 0, performance = 0, quality = 0 }) {
  const oee = availability * performance * quality

  const arcs = [
    { value: availability, color: colors.success, label: 'Disponibilidade', radius: RADIUS },
    { value: performance, color: colors.primary, label: 'Performance', radius: RADIUS - STROKE - 4 },
    { value: quality, color: colors.secondary, label: 'Qualidade', radius: RADIUS - (STROKE + 4) * 2 },
  ]

  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
      <svg width={SIZE} height={SIZE} viewBox={`0 0 ${SIZE} ${SIZE}`}>
        {/* Background arcs */}
        {arcs.map((arc, i) => (
          <circle
            key={`bg-${i}`}
            cx={SIZE / 2}
            cy={SIZE / 2}
            r={arc.radius}
            fill="none"
            stroke={colors.surfaceVariant}
            strokeWidth={STROKE}
          />
        ))}

        {/* Value arcs */}
        {arcs.map((arc, i) => (
          <Arc key={i} value={arc.value} color={arc.color} offset={0} radius={arc.radius} />
        ))}

        {/* Center text */}
        <text
          x={SIZE / 2}
          y={SIZE / 2 - 8}
          textAnchor="middle"
          style={{ ...typography.displaySmall, fill: colors.onSurface }}
        >
          {(oee * 100).toFixed(1)}%
        </text>
        <text
          x={SIZE / 2}
          y={SIZE / 2 + 16}
          textAnchor="middle"
          style={{ ...typography.labelMedium, fill: colors.onSurfaceVariant }}
        >
          OEE
        </text>
      </svg>

      {/* Legend */}
      <div style={{ display: 'flex', gap: '16px', marginTop: '8px' }}>
        {arcs.map((arc, i) => (
          <div key={i} style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
            <div style={{ width: 8, height: 8, borderRadius: '50%', background: arc.color }} />
            <span style={{ ...typography.labelSmall, color: colors.onSurfaceVariant }}>
              {arc.label}: {(arc.value * 100).toFixed(0)}%
            </span>
          </div>
        ))}
      </div>
    </div>
  )
}
