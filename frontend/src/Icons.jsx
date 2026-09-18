const stroke = { fill: 'none', stroke: 'currentColor', strokeWidth: 1.6, strokeLinecap: 'round', strokeLinejoin: 'round' }

export function IconSkip(props) {
  return (
    <svg viewBox="0 0 20 20" width="18" height="18" {...props}>
      <path d="M5 4v12M7 10l8-6v12l-8-6Z" {...stroke} />
    </svg>
  )
}

export function IconClose(props) {
  return (
    <svg viewBox="0 0 20 20" width="14" height="14" {...props}>
      <path d="M5 5l10 10M15 5L5 15" {...stroke} />
    </svg>
  )
}

export function IconPlayFilled(props) {
  return (
    <svg viewBox="0 0 20 20" width="20" height="20" {...props}>
      <path d="M6 4l11 6-11 6V4Z" fill="currentColor" />
    </svg>
  )
}

export function IconPause(props) {
  return (
    <svg viewBox="0 0 20 20" width="20" height="20" {...props}>
      <rect x="5" y="4" width="4" height="12" fill="currentColor" />
      <rect x="11" y="4" width="4" height="12" fill="currentColor" />
    </svg>
  )
}

export function IconPrevious(props) {
  return (
    <svg viewBox="0 0 20 20" width="18" height="18" {...props}>
      <path d="M15 4v12M13 10L5 4v12l8-6Z" {...stroke} />
    </svg>
  )
}

export function IconChevronUp(props) {
  return (
    <svg viewBox="0 0 20 20" width="13" height="13" {...props}>
      <path d="M4 12l6-6 6 6" {...stroke} />
    </svg>
  )
}

export function IconChevronDown(props) {
  return (
    <svg viewBox="0 0 20 20" width="13" height="13" {...props}>
      <path d="M4 8l6 6 6-6" {...stroke} />
    </svg>
  )
}

export function IconStar({ filled, ...props }) {
  return (
    <svg viewBox="0 0 20 20" width="20" height="20" {...props}>
      <path
        d="M10 2.5l2.35 4.76 5.25.76-3.8 3.7.9 5.23L10 14.5l-4.7 2.45.9-5.23-3.8-3.7 5.25-.76L10 2.5Z"
        fill={filled ? 'currentColor' : 'none'}
        stroke="currentColor"
        strokeWidth="1.4"
        strokeLinejoin="round"
      />
    </svg>
  )
}
