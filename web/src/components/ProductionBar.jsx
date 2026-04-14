/**
 * ProductionBar — Barras de produção por hora com linha de meta.
 */

import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ReferenceLine, ResponsiveContainer, Cell } from 'recharts'
import { colors, typography } from '../styles/theme'

export default function ProductionBar({ data = [], targetPerHour = 0 }) {
  return (
    <div>
      <p style={{ ...typography.titleSmall, color: colors.onSurface, marginBottom: '8px' }}>
        Peças / Hora
      </p>
      <ResponsiveContainer width="100%" height={250}>
        <BarChart data={data} margin={{ top: 5, right: 10, left: 0, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke={colors.outlineVariant} />
          <XAxis
            dataKey="hour"
            tick={{ ...typography.labelSmall, fill: colors.onSurfaceVariant }}
          />
          <YAxis
            tick={{ ...typography.labelSmall, fill: colors.onSurfaceVariant }}
          />
          <Tooltip
            contentStyle={{
              background: '#FFFFFF',
              border: `1px solid ${colors.outlineVariant}`,
              borderRadius: '8px',
              ...typography.bodySmall,
            }}
          />
          <Bar dataKey="parts_ok" radius={[4, 4, 0, 0]} maxBarSize={40}>
            {data.map((entry, i) => (
              <Cell
                key={i}
                fill={
                  entry.parts_ok >= targetPerHour
                    ? colors.success
                    : entry.parts_ok >= targetPerHour * 0.7
                    ? colors.warning
                    : colors.error
                }
              />
            ))}
          </Bar>
          {targetPerHour > 0 && (
            <ReferenceLine
              y={targetPerHour}
              stroke={colors.primary}
              strokeDasharray="5 5"
              label={{
                value: `Meta: ${targetPerHour}`,
                position: 'right',
                fill: colors.primary,
                ...typography.labelSmall,
              }}
            />
          )}
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}
