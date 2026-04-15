/**
 * ME2Logo — Animated logo where the "2" flips and morphs into "S",
 * creating the visual allusion: ME2 ↔ MES (Manufacturing Execution System).
 *
 * Technique: 3D Y-axis flip with character swap at the midpoint.
 * When the flip reaches 90° (edge-on, character invisible),
 * "2" swaps to "S" seamlessly.
 */

import { useState, useEffect, useRef } from 'react'
import { colors, typography } from '../styles/theme'

const SHOW_2_MS = 3000      // time showing "2" before flipping
const FLIP_MS = 600         // flip transition duration
const SHOW_S_MS = 800       // time showing "S" at peak

const PHASES = [
  { name: 'idle',       duration: SHOW_2_MS, rotation: 0,   char: '2' },
  { name: 'flip-to-s',  duration: FLIP_MS,   rotation: 90,  char: '2' },
  { name: 'show-s',     duration: SHOW_S_MS, rotation: 180, char: 'S' },
  { name: 'flip-to-2',  duration: FLIP_MS,   rotation: 270, char: 'S' },
]

export default function ME2Logo({
  size = 32,
  color,
  light = false,
  animated = true,
  style = {},
}) {
  const textColor = light ? '#FFFFFF' : (color || colors.meitech)
  const [phaseIdx, setPhaseIdx] = useState(0)
  const cancelledRef = useRef(false)

  useEffect(() => {
    if (!animated) return

    cancelledRef.current = false
    let timer = null

    function step(idx) {
      if (cancelledRef.current) return
      setPhaseIdx(idx)
      timer = setTimeout(() => {
        step((idx + 1) % PHASES.length)
      }, PHASES[idx].duration)
    }

    step(0)

    return () => {
      cancelledRef.current = true
      clearTimeout(timer)
    }
  }, [animated])

  const phase = PHASES[phaseIdx]

  const fontDef = "'Baloo 2', cursive"

  const meStyle = {
    fontFamily: fontDef,
    fontSize: size,
    fontWeight: 800,
    color: textColor,
    lineHeight: 1,
    letterSpacing: `${size * 0.12}px`,
  }

  const flipStyle = {
    fontFamily: fontDef,
    fontSize: size,
    fontWeight: 800,
    color: textColor,
    lineHeight: 1,
    display: 'inline-block',
    width: `${size * 0.65}px`,
    textAlign: 'center',
    transform: `rotateY(${phase.rotation}deg)`,
    transition: phase.name === 'idle' ? 'none' : `transform ${FLIP_MS}ms ease-in-out`,
    transformOrigin: 'center',
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
      <span style={meStyle}>ME</span>
      <span style={flipStyle}>{phase.char}</span>
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
      fontFamily: "'Baloo 2', cursive",
      fontSize: size,
      fontWeight: 800,
      color: textColor,
      lineHeight: 1,
      ...style,
    }}>
      ME2
    </span>
  )
}
