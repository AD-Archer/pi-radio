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
