import { useEffect, useState } from 'react'
import { api } from './api'
import { useToast } from './ToastContext'

function formatTime(iso) {
  const d = new Date(iso)
  return d.toLocaleString(undefined, { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' })
}

export default function Activity() {
  const [entries, setEntries] = useState(null)
  const toast = useToast()

  useEffect(() => {
    api.auditLog()
      .then(setEntries)
      .catch((e) => {
        toast(`Couldn't load activity: ${e.message}`, 'error')
        setEntries([])
      })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  if (entries === null) {
    return <p className="empty">Loading…</p>
  }

  return (
    <div>
      {entries.length === 0 && <p className="empty">Nothing logged yet.</p>}
      {entries.map((e, i) => (
        <div key={i} className="audit-row">
          <div>
            <strong>{e.username}</strong> {e.action}
          </div>
          <div className="audit-meta">
            {formatTime(e.timestamp)}
            {e.details ? ` · ${e.details}` : ''}
          </div>
        </div>
      ))}
    </div>
  )
}
