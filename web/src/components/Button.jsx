/**
 * ME2 Button — Material Design 3 button variants.
 */

import { colors, shape, typography } from '../styles/theme'

const variants = {
  filled: {
    background: colors.primary,
    color: colors.onPrimary,
    border: 'none',
  },
  outlined: {
    background: 'transparent',
    color: colors.primary,
    border: `1px solid ${colors.outline}`,
  },
  text: {
    background: 'transparent',
    color: colors.primary,
    border: 'none',
  },
  tonal: {
    background: colors.secondaryContainer,
    color: colors.onSecondaryContainer,
    border: 'none',
  },
  error: {
    background: colors.error,
    color: colors.onError,
    border: 'none',
  },
}

export default function Button({
  children,
  variant = 'filled',
  disabled = false,
  onClick,
  style,
  ...props
}) {
  const v = variants[variant] || variants.filled

  return (
    <button
      style={{
        ...v,
        ...typography.labelLarge,
        padding: '10px 24px',
        borderRadius: shape.full,
        cursor: disabled ? 'not-allowed' : 'pointer',
        opacity: disabled ? 0.5 : 1,
        display: 'inline-flex',
        alignItems: 'center',
        gap: '8px',
        transition: 'opacity 0.15s',
        ...style,
      }}
      onClick={disabled ? undefined : onClick}
      disabled={disabled}
      {...props}
    >
      {children}
    </button>
  )
}
