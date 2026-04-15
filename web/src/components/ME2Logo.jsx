/**
 * ME2Logo — Animated logo where the "2" flips to reveal a mirrored "S",
 * creating a visual allusion: ME2 ↔ MES (Manufacturing Execution System).
 *
 * The "2" rotates on the Y-axis (3D flip). At 180° it becomes a mirrored "2"
 * which resembles an "S", briefly showing "MES" before flipping back.
 */

import { colors, typography } from '../styles/theme'

const FLIP_DURATION = 8     // seconds per full cycle
const PAUSE_AT_2 = 65       // % of cycle showing "2"
const PAUSE_AT_S = 85       // % where it pauses as "S"

// Keyframes: stay as "2" most of the time, flip to "S" briefly, flip back
const flipKeyframes = `
@keyframes me2flip {
  0%   { transform: rotateY(0deg); }
  ${PAUSE_AT_2}%  { transform: rotateY(0deg); }
  ${PAUSE_AT_2 + 8}%  { transform: rotateY(180deg); }
  ${PAUSE_AT_S}%  { transform: rotateY(180deg); }
  ${PAUSE_AT_S + 8}%  { transform: rotateY(360deg); }
  100% { transform: rotateY(360deg); }
}
`

export default function ME2Logo({
  size = 32,
  color = colors.meitech,
  light = false,
  style = {},
}) {
  const textColor = light ? '#FFFFFF' : color
  const letterStyle = {
    fontFamily: typography.brandFamily,
    fontSize: size,
    fontWeight: 700,
    color: textColor,
    lineHeight: 1,
    letterSpacing: '-0.5px',
    display: 'inline-block',
  }

  return (
    <>
      <style>{flipKeyframes}</style>
      <span
        style={{
          display: 'inline-flex',
          alignItems: 'baseline',
          perspective: '400px',
          ...style,
        }}
      >
        {/* "ME" — static */}
        <span style={letterStyle}>ME</span>

        {/* "2" — flips to mirrored "S" */}
        <span
          style={{
            ...letterStyle,
            display: 'inline-block',
            animation: `me2flip ${FLIP_DURATION}s ease-in-out infinite`,
            transformStyle: 'preserve-3d',
            backfaceVisibility: 'visible',
          }}
        >
          2
        </span>
      </span>
    </>
  )
}

/**
 * Compact version for the Nav Rail (small, white, no animation delay).
 */
export function ME2LogoCompact({ size = 16 }) {
  return <ME2Logo size={size} light style={{ letterSpacing: '-0.3px' }} />
}
