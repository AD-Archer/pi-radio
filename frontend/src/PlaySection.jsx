import { useState } from 'react'
import { api } from './api'
import { useSearch } from './useSearch'
import { useToast } from './ToastContext'

const DURATIONS = [
  { value: 'once', label: 'until it finishes' },
  { value: '15', label: 'loop for 15 min' },
  { value: '30', label: 'loop for 30 min' },
  { value: '60', label: 'loop for 1 hour' },
  { value: '120', label: 'loop for 2 hours' },
  { value: '240', label: 'loop for 4 hours' },
  { value: 'forever', label: 'loop until changed' },
]

export default function PlaySection() {
  const { query, setQuery, results, error } = useSearch((q) => api.playlists(q), { debounceMs: 250 })
  const [duration, setDuration] = useState('once')
  const [busy, setBusy] = useState(null)
  const toast = useToast()

  async function play(p) {
    setBusy(`${p.id}:play`)
    try {
      const once = duration === 'once'
      const minutes = once || duration === 'forever' ? null : parseInt(duration, 10)
      const r = await api.playPlaylist(p.id, p.name, { once, minutes })
      toast(`Playing "${p.name}" · ${r.queued} tracks`)
    } catch (e) {
      toast(`Couldn't play: ${e.message}`, 'error')
    } finally {
      setBusy(null)
    }
  }

  async function queueNext(p) {
    setBusy(`${p.id}:queue`)
    try {
      const r = await api.queuePlaylistNext(p.id)
      toast(`Queued "${p.name}" next · ${r.queued} tracks`)
    } catch (e) {
      toast(`Couldn't queue: ${e.message}`, 'error')
    } finally {
      setBusy(null)
    }
  }

  return (
    <div>
      <div className="field-row">
        <input type="text" placeholder="Search playlists…" value={query} onChange={(e) => setQuery(e.target.value)} />
      </div>
      <div className="field-row">
        <label className="inline-label" htmlFor="play-duration">
          "Play now" plays
        </label>
        <select id="play-duration" value={duration} onChange={(e) => setDuration(e.target.value)}>
          {DURATIONS.map((d) => (
            <option key={d.value} value={d.value}>
              {d.label}
            </option>
          ))}
        </select>
      </div>

      {error && <p className="empty">Couldn't load playlists: {error}</p>}
      {!error && query && results.length === 0 && <p className="empty">No playlists found.</p>}

      <ul className="result-list">
        {results.map((p) => (
          <li key={p.id} className="result-row">
            <span className="result-name">
              {p.name}
              <span className="result-count mono">{p.songCount}</span>
            </span>
            <span className="result-actions">
              <button className="btn-sm" disabled={busy === `${p.id}:queue`} onClick={() => queueNext(p)} title="Play right after the current track, don't disturb anything else">
                Queue next
              </button>
              <button className="btn-sm btn-primary" disabled={busy === `${p.id}:play`} onClick={() => play(p)}>
                Play now
              </button>
            </span>
          </li>
        ))}
      </ul>
    </div>
  )
}
