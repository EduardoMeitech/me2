/**
 * ME2 Design System — Material Design 3 + Meitech Visual Identity
 * "Keep Moving" — Sempre em Movimento
 */

export const colors = {
  // Primary — Meitech Blue
  primary: '#0066CC',
  onPrimary: '#FFFFFF',
  primaryContainer: '#D6E4FF',
  onPrimaryContainer: '#001B3D',

  // Secondary — Operational Green ("Keep Moving")
  secondary: '#00A878',
  onSecondary: '#FFFFFF',
  secondaryContainer: '#C6F1E0',
  onSecondaryContainer: '#002114',

  // Error — Critical Stop
  error: '#D32F2F',
  onError: '#FFFFFF',
  errorContainer: '#FFDAD6',
  errorDark: '#7B0000',

  // Warning — Attention / Setup
  warning: '#F57C00',
  warningLight: '#F9A825',
  warningDark: '#E65100',

  // Success — Uptime / Running
  success: '#388E3C',
  onSuccess: '#FFFFFF',

  // Surface
  surface: '#F4F6FB',
  onSurface: '#1A1C1E',
  surfaceVariant: '#E0E2EC',
  onSurfaceVariant: '#44474E',

  // Outline
  outline: '#72777F',
  outlineVariant: '#C2C6CF',

  // Background
  background: '#EEF1F8',
  onBackground: '#1A1C1E',

  // Inverse
  inverseSurface: '#2F3033',
  inverseOnSurface: '#F1F0F4',
}

/**
 * WordStatus → color mapping
 * Machine state bitmask from FB_ME2Status in PLC
 */
export const statusColors = {
  18: { color: colors.success, label: 'Uptime', token: 'success' },
  16: { color: colors.warningLight, label: 'Idle', token: 'warning-light' },
  17: { color: '#5C6BC0', label: 'Parada Planejada', token: 'planned' },
  20: { color: '#00897B', label: 'Starving', token: 'secondary' },
  24: { color: colors.warningDark, label: 'Blocked', token: 'warning-dark' },
  26: { color: colors.warningLight, label: 'Idle', token: 'warning-light' },
  28: { color: colors.warningLight, label: 'Idle', token: 'warning-light' },
  30: { color: '#00897B', label: 'Starving', token: 'secondary' },
  32: { color: colors.error, label: 'Falha', token: 'error' },
  64: { color: colors.primary, label: 'Setup', token: 'primary' },
  128: { color: colors.errorDark, label: 'Emergência', token: 'error-dark' },
}

export function getStatusColor(wordStatus) {
  return statusColors[wordStatus]?.color ?? colors.outline
}

export function getStatusLabel(wordStatus) {
  return statusColors[wordStatus]?.label ?? `Status ${wordStatus}`
}

export const typography = {
  fontFamily: "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
  displayLarge: { fontSize: '57px', fontWeight: 400, lineHeight: '64px', letterSpacing: '-0.25px' },
  displayMedium: { fontSize: '45px', fontWeight: 400, lineHeight: '52px' },
  displaySmall: { fontSize: '36px', fontWeight: 400, lineHeight: '44px' },
  headlineLarge: { fontSize: '32px', fontWeight: 600, lineHeight: '40px' },
  headlineMedium: { fontSize: '28px', fontWeight: 600, lineHeight: '36px' },
  headlineSmall: { fontSize: '24px', fontWeight: 600, lineHeight: '32px' },
  titleLarge: { fontSize: '22px', fontWeight: 500, lineHeight: '28px' },
  titleMedium: { fontSize: '16px', fontWeight: 500, lineHeight: '24px', letterSpacing: '0.15px' },
  titleSmall: { fontSize: '14px', fontWeight: 500, lineHeight: '20px', letterSpacing: '0.1px' },
  bodyLarge: { fontSize: '16px', fontWeight: 400, lineHeight: '24px', letterSpacing: '0.5px' },
  bodyMedium: { fontSize: '14px', fontWeight: 400, lineHeight: '20px', letterSpacing: '0.25px' },
  bodySmall: { fontSize: '12px', fontWeight: 400, lineHeight: '16px', letterSpacing: '0.4px' },
  labelLarge: { fontSize: '14px', fontWeight: 500, lineHeight: '20px', letterSpacing: '0.1px' },
  labelMedium: { fontSize: '12px', fontWeight: 500, lineHeight: '16px', letterSpacing: '0.5px' },
  labelSmall: { fontSize: '11px', fontWeight: 500, lineHeight: '16px', letterSpacing: '0.5px' },
}

export const shape = {
  none: '0px',
  extraSmall: '4px',
  small: '8px',
  medium: '12px',
  large: '16px',
  extraLarge: '28px',
  full: '9999px',
}

export const elevation = {
  level0: 'none',
  level1: '0 1px 2px rgba(0,0,0,0.3), 0 1px 3px 1px rgba(0,0,0,0.15)',
  level2: '0 1px 2px rgba(0,0,0,0.3), 0 2px 6px 2px rgba(0,0,0,0.15)',
  level3: '0 4px 8px 3px rgba(0,0,0,0.15), 0 1px 3px rgba(0,0,0,0.3)',
}

/**
 * Shift definitions — Meitech standard
 * T100: 05:00-13:29 | T200: 13:30-21:59 | T300: 22:00-04:59
 */
export const shifts = {
  T100: { name: 'Turno 1', start: '05:00', end: '13:29', minutes: 509 },
  T200: { name: 'Turno 2', start: '13:30', end: '21:59', minutes: 509 },
  T300: { name: 'Turno 3', start: '22:00', end: '04:59', minutes: 420 },
}

export function getCurrentShift() {
  const now = new Date()
  const h = now.getHours()
  const m = now.getMinutes()
  const totalMin = h * 60 + m

  if (totalMin >= 300 && totalMin <= 809) return 'T100'   // 05:00 - 13:29
  if (totalMin >= 810 && totalMin <= 1319) return 'T200'  // 13:30 - 21:59
  return 'T300'                                            // 22:00 - 04:59
}
