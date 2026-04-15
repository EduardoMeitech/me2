/**
 * ME2 Design System — Material Design 3 + Meitech Visual Identity
 * Ported from RADAR v9 with ME2-specific status mappings
 * "Keep Moving" — Sempre em Movimento
 */

// ---------------------------------------------------------------------------
// CORES (MD3 Palette + Meitech Brand)
// ---------------------------------------------------------------------------
export const colors = {
  // Primary
  primary:            '#0066CC',
  onPrimary:          '#FFFFFF',
  primaryContainer:   '#D6E4FF',
  onPrimaryContainer: '#001D36',

  // Secondary
  secondary:            '#535F70',
  secondaryContainer:   '#D7E3F7',
  onSecondaryContainer: '#101C2B',

  // Surface & Background
  surface:          '#F8F9FF',
  surfaceVariant:   '#DFE2EB',
  background:       '#F0F2F8',
  onSurface:        '#1A1C1E',
  onSurfaceVariant: '#43474E',

  // Outline
  outline:        '#73777F',
  outlineVariant: '#C3C6CF',

  // Error
  error:            '#BA1A1A',
  errorContainer:   '#FFDAD6',
  onError:          '#FFFFFF',
  onErrorContainer: '#410002',
  errorDark:        '#7B0000',

  // Warning
  warning:      '#F57C00',
  warningLight: '#F9A825',
  warningDark:  '#E65100',

  // Success
  success:   '#388E3C',
  onSuccess: '#FFFFFF',

  // Meitech brand
  meitech:     '#0040f0',
  meitechDark: '#0030c0',

  // ME2 accent (operational green)
  me2Green: '#00A878',
}

// ---------------------------------------------------------------------------
// WordStatus → color mapping (FB_ME2Status bitmask from PLC)
// ---------------------------------------------------------------------------
export const statusColors = {
  18:  { color: colors.success,      label: 'Uptime',           token: 'success' },
  16:  { color: colors.warningLight, label: 'Idle',             token: 'warning-light' },
  17:  { color: '#5C6BC0',          label: 'Parada Planejada', token: 'planned' },
  20:  { color: '#00897B',          label: 'Starving',         token: 'secondary' },
  24:  { color: colors.warningDark,  label: 'Blocked',          token: 'warning-dark' },
  26:  { color: colors.warningLight, label: 'Idle',             token: 'warning-light' },
  28:  { color: colors.warningLight, label: 'Idle',             token: 'warning-light' },
  30:  { color: '#00897B',          label: 'Starving',         token: 'secondary' },
  32:  { color: colors.error,        label: 'Falha',            token: 'error' },
  64:  { color: colors.primary,      label: 'Setup',            token: 'primary' },
  128: { color: colors.errorDark,    label: 'Emergência',       token: 'error-dark' },
}

export function getStatusColor(wordStatus) {
  return statusColors[wordStatus]?.color ?? colors.outline
}

export function getStatusLabel(wordStatus) {
  return statusColors[wordStatus]?.label ?? `Status ${wordStatus}`
}

// ---------------------------------------------------------------------------
// TIPOGRAFIA (MD3 Type Scale)
// ---------------------------------------------------------------------------
export const typography = {
  fontFamily: "'Segoe UI', Roboto, Arial, sans-serif",
  brandFamily: "'Amina', sans-serif",

  displayLarge:  { fontSize: '57px', fontWeight: 700, letterSpacing: '-0.25px', lineHeight: 1.12 },
  displayMedium: { fontSize: '45px', fontWeight: 700, lineHeight: 1.16 },
  displaySmall:  { fontSize: '36px', fontWeight: 700, lineHeight: 1.22 },
  headlineLarge:  { fontSize: '32px', fontWeight: 700, lineHeight: 1.25 },
  headlineMedium: { fontSize: '28px', fontWeight: 600, lineHeight: 1.29 },
  headlineSmall:  { fontSize: '24px', fontWeight: 600, lineHeight: 1.33 },
  titleLarge:  { fontSize: '22px', fontWeight: 500, lineHeight: 1.27 },
  titleMedium: { fontSize: '16px', fontWeight: 500, letterSpacing: '0.15px', lineHeight: 1.5 },
  titleSmall:  { fontSize: '14px', fontWeight: 500, letterSpacing: '0.1px', lineHeight: 1.43 },
  bodyLarge:  { fontSize: '16px', fontWeight: 400, letterSpacing: '0.5px', lineHeight: 1.5 },
  bodyMedium: { fontSize: '14px', fontWeight: 400, letterSpacing: '0.25px', lineHeight: 1.43 },
  bodySmall:  { fontSize: '12px', fontWeight: 400, letterSpacing: '0.4px', lineHeight: 1.33 },
  labelLarge:  { fontSize: '14px', fontWeight: 500, letterSpacing: '0.1px', lineHeight: 1.43 },
  labelMedium: { fontSize: '12px', fontWeight: 500, letterSpacing: '0.5px', lineHeight: 1.33 },
  labelSmall:  { fontSize: '11px', fontWeight: 500, letterSpacing: '0.5px', lineHeight: 1.45 },
}

// ---------------------------------------------------------------------------
// ELEVAÇÕES (MD3)
// ---------------------------------------------------------------------------
export const elevation = {
  level0: 'none',
  level1: '0px 1px 2px rgba(0,0,0,0.3), 0px 1px 3px 1px rgba(0,0,0,0.15)',
  level2: '0px 1px 2px rgba(0,0,0,0.3), 0px 2px 6px 2px rgba(0,0,0,0.15)',
  level3: '0px 1px 3px rgba(0,0,0,0.3), 0px 4px 8px 3px rgba(0,0,0,0.15)',
  level4: '0px 2px 3px rgba(0,0,0,0.3), 0px 6px 10px 4px rgba(0,0,0,0.15)',
}

// ---------------------------------------------------------------------------
// SHAPE (MD3 Shape Scale)
// ---------------------------------------------------------------------------
export const shape = {
  none: '0px',
  extraSmall: '4px',
  small: '8px',
  medium: '12px',
  large: '16px',
  extraLarge: '28px',
  full: '9999px',
}

// ---------------------------------------------------------------------------
// LAYOUT
// ---------------------------------------------------------------------------
export const layout = {
  railWidth: 88,
  headerHeight: 64,
  navHeight: 80,
  maxWidth: 1200,
}

// ---------------------------------------------------------------------------
// Shifts — Meitech standard
// ---------------------------------------------------------------------------
export const shifts = {
  T100: { name: 'Turno 1', start: '05:00', end: '13:29', minutes: 509 },
  T200: { name: 'Turno 2', start: '13:30', end: '21:59', minutes: 509 },
  T300: { name: 'Turno 3', start: '22:00', end: '04:59', minutes: 420 },
}

export function getCurrentShift() {
  const now = new Date()
  const totalMin = now.getHours() * 60 + now.getMinutes()
  if (totalMin >= 300 && totalMin <= 809) return 'T100'
  if (totalMin >= 810 && totalMin <= 1319) return 'T200'
  return 'T300'
}
