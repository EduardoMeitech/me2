/**
 * ME2Logo — Animated logo where the "2" flips and morphs into "S",
 * creating the visual allusion: ME2 ↔ MES (Manufacturing Execution System).
 *
 * Technique: 3D Y-axis flip with character swap at the midpoint.
 * Front face = "2", back face = "S". When the flip reaches 90° (edge-on),
 * the character swaps seamlessly. The "S" is shown mirrored (scaleX -1)
 * so it appears correctly when the back face is visible.
 */

import { useState, useEffect, useRef } from 'react'
import { colors, typography } from '../styles/theme'

const CYCLE_MS = 5000       // total cycle duration
const SHOW_2_MS = 3000      // time showing "2" before flipping
const FLIP_MS = 600         // flip transition duration
const SHOW_S_MS = 800       // time showing "S" at peak

export default function ME2Logo({
  size = 32,
  color,
  light = false,
  animated = true,
  style = {},
}) {
  const textColor = light ? '#FFFFFF' : (color || colors.meitech)
  const [phase, setPhase] = useState('idle') // idle | flip-to-s | show-s | flip-to-2
  const timerRef = useRef(null)

  useEffect(() => {
    if (!animated) return

    function cycle() {
      // Phase 1: Show "2" (idle)
      setPhase('idle')

      timerRef.current = setTimeout(() => {
        // Phase 2: Flip to "S"
        setPhase('flip-to-s')

        timerRef.current = setTimeout(() => {
          // Phase 3: Show "S"
          setPhase('show-s')

          timerRef.current = setTimeout(() => {
            // Phase 4: Flip back to "2"
            setPhase('flip-to-2')

            timerRef.current = setTimeout(() => {
              cycle() // restart
            }, FLIP_MS)
          }, SHOW_S_MS)
        }, FLIP_MS)
      }, SHOW_2_MS)
    }

    cycle()
    return () => clearTimeout(timerRef.current)
  }, [animated])

  const isShowingS = phase === 'show-s' || phase === 'flip-to-2'

  // Rotation angles per phase
  const rotation =
    phase === 'idle' ? 0 :
    phase === 'flip-to-s' ? 90 :
    phase === 'show-s' ? 180 :
    phase === 'flip-to-2' ? 270 : 0

  const baseStyle = {
    fontFamily: typography.brandFamily,
    fontSize: size,
    fontWeight: 700,
    color: textColor,
    lineHeight: 1,
    letterSpacing: '-0.5px',
    display: 'inline-block',
  }

  return (
    <span
      style={{
        display: 'inline-flex',
        alignItems: 'baseline',
        perspective: '600px',
        ...style,
      }}
    >
      {/* "ME" — static */}
      <span style={baseStyle}>ME</span>

      {/* "2" / "S" — animated flip with character swap */}
      <span
        style={{
          ...baseStyle,
          display: 'inline-block',
          transform: `rotateY(${rotation}deg)`,
          transition: phase === 'idle' ? 'none' : `transform ${FLIP_MS}ms ease-in-out`,
          transformOrigin: 'center',
        }}
      >
        {isShowingS ? 'S' : '2'}
      </span>
    </span>
  )
}

/**
 * Static version — no animation. Used in footer and other static contexts.
 */
export function ME2LogoStatic({ size = 15, color, light = false, style = {} }) {
  const textColor = light ? '#FFFFFF' : (color || colors.meitech)
  return (
    <span style={{
      fontFamily: typography.brandFamily,
      fontSize: size,
      fontWeight: 700,
      color: textColor,
      lineHeight: 1,
      letterSpacing: '-0.5px',
      ...style,
    }}>
      ME2
    </span>
  )
}
