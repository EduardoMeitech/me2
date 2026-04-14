/**
 * ShiftSelector — Toggle T1/T2/T3 com horários.
 */

import { colors, typography, shape, shifts, getCurrentShift } from '../styles/theme'

export default function ShiftSelector({ selected, onChange }) {
  const currentShift = getCurrentShift()

  return (
    <div style={{ display: 'flex', gap: '8px' }}>
      {Object.entries(shifts).map(([key, shift]) => {
        const isSelected = selected === key || (!selected && key === currentShift)

        return (
          <button
            key={key}
            onClick={() => onChange(key === selected ? null : key)}
            style={{
              padding: '8px 16px',
              borderRadius: shape.full,
              border: isSelected ? 'none' : `1px solid ${colors.outlineVariant}`,
              background: isSelected ? colors.primary : 'transparent',
              color: isSelected ? colors.onPrimary : colors.onSurface,
              cursor: 'pointer',
              ...typography.labelMedium,
              transition: 'all 0.2s',
            }}
          >
            <span>{shift.name}</span>
            <span style={{ opacity: 0.7, marginLeft: '4px' }}>
              {shift.start}-{shift.end}
            </span>
          </button>
        )
      })}
    </div>
  )
}
