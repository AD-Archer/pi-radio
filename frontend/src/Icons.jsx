const stroke = { fill: 'none', stroke: 'currentColor', strokeWidth: 1.6, strokeLinecap: 'round', strokeLinejoin: 'round' }

export function IconSkip(props) {
  return (
    <svg viewBox="0 0 20 20" width="16" height="16" {...props}>
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
