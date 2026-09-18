export default function TitleBar({ title, onBack, live }) {
  return (
    <div className="titlebar">
      <div className="titlebar-side">
        {onBack && (
          <button className="titlebar-back" onClick={onBack}>
            <span className="titlebar-chevron">‹</span> Menu
          </button>
        )}
      </div>
      <span className="titlebar-title">{title}</span>
      <div className="titlebar-side titlebar-side-right">
        <span className={live ? 'titlebar-dot titlebar-dot-live' : 'titlebar-dot'} />
      </div>
    </div>
  )
}
