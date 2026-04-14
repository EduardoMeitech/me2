/**
 * ME2 Card — Material Design 3 card component.
 */

import { colors, shape, elevation } from '../styles/theme'

const variants = {
  elevated: {
    background: '#FFFFFF',
    boxShadow: elevation.level1,
    border: 'none',
  },
  filled: {
    background: colors.surfaceVariant,
    boxShadow: 'none',
    border: 'none',
  },
  outlined: {
    background: '#FFFFFF',
    boxShadow: 'none',
    border: `1px solid ${colors.outlineVariant}`,
  },
}

export default function Card({ children, variant = 'elevated', style, onClick, ...props }) {
  const v = variants[variant] || variants.elevated

  return (
    <div
      style={{
        borderRadius: shape.medium,
        padding: '16px',
        ...v,
        cursor: onClick ? 'pointer' : 'default',
        transition: 'box-shadow 0.2s, transform 0.1s',
        ...style,
      }}
      onClick={onClick}
      {...props}
    >
      {children}
    </div>
  )
}
