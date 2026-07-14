// Inline SVG icons (no external assets — works behind a strict CSP). Stroke-based line icons;
// path data ported from design_handoff_floated/. Each takes a `size` and passes through props.

function Svg({ size = 20, stroke = 2, fill = 'none', children, ...rest }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill={fill}
      stroke={fill === 'none' ? 'currentColor' : 'none'}
      strokeWidth={stroke}
      strokeLinecap="round"
      strokeLinejoin="round"
      {...rest}
    >
      {children}
    </svg>
  )
}

// Brand mark: a gentle wave with a dot floating above — "staying afloat".
export function Wave({ size = 24, color = 'currentColor', stroke = 2.2, ...rest }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" {...rest}>
      <path
        d="M3 15.5c2.3-2 4.4-2 6.5 0s4.2 2 6.5 0 4.2-2 6.5 0"
        stroke={color}
        strokeWidth={stroke}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <circle cx="12" cy="8" r="2.7" fill={color} />
    </svg>
  )
}

export const Check = (p) => (
  <Svg stroke={3.5} {...p}>
    <path d="M5 13l4 4L19 7" />
  </Svg>
)

export const TriangleAlert = (p) => (
  <Svg stroke={2.4} {...p}>
    <path d="M12 3.5l9.5 16.5H2.5z" />
    <path d="M12 10v4.5M12 17.6v.01" />
  </Svg>
)

export const XMark = (p) => (
  <Svg stroke={3} {...p}>
    <path d="M6 6l12 12M18 6L6 18" />
  </Svg>
)

export const AlertCircle = (p) => (
  <Svg stroke={2.2} {...p}>
    <circle cx="12" cy="12" r="9" />
    <path d="M12 8v5M12 16.5v.01" />
  </Svg>
)

export const ArrowRight = (p) => (
  <Svg {...p}>
    <path d="M5 12h14M13 6l6 6-6 6" />
  </Svg>
)

export const ArrowUp = (p) => (
  <Svg stroke={2.4} {...p}>
    <path d="M12 19V5M5 12l7-7 7 7" />
  </Svg>
)

export const Flag = (p) => (
  <Svg stroke={2.4} {...p}>
    <path d="M4 21V4M4 4l14 3-4 4 4 4-14 3" />
  </Svg>
)

export const Sun = (p) => (
  <Svg {...p}>
    <circle cx="12" cy="12" r="4" />
    <path d="M12 2v2M12 20v2M2 12h2M20 12h2M5 5l1.4 1.4M17.6 17.6L19 19M19 5l-1.4 1.4M6.4 17.6L5 19" />
  </Svg>
)

export const Moon = ({ size = 18, ...rest }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="currentColor" {...rest}>
    <path d="M21 12.8A8 8 0 1 1 11.2 3 6 6 0 0 0 21 12.8Z" />
  </svg>
)

export const Shield = (p) => (
  <Svg {...p}>
    <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10Z" />
  </Svg>
)

export const Mail = (p) => (
  <Svg {...p}>
    <path d="M3.5 6.5h17v11h-17z" />
    <path d="M3.5 6.5l8.5 6.5 8.5-6.5" />
  </Svg>
)

export const LogOut = (p) => (
  <Svg {...p}>
    <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
    <path d="M16 17l5-5-5-5" />
    <path d="M21 12H9" />
  </Svg>
)

export const ChatTab = (p) => (
  <Svg {...p}>
    <path d="M4 5.5h16a1.5 1.5 0 0 1 1.5 1.5v8a1.5 1.5 0 0 1-1.5 1.5H9l-4.5 4V7A1.5 1.5 0 0 1 6 5.5z" />
  </Svg>
)

export const BarsTab = (p) => (
  <Svg {...p}>
    <path d="M4 20V11M10 20V4M16 20v-6M22 20H2" />
  </Svg>
)

// Verdict pill icon by verdict value — always paired with the word (never color alone).
export function VerdictIcon({ verdict, size = 15 }) {
  if (verdict === 'yes') return <Check size={size} stroke={3} />
  if (verdict === 'no') return <XMark size={size} stroke={3} />
  return <TriangleAlert size={size} />
}
