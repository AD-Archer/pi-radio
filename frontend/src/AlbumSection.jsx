import { useState } from 'react'
import { api } from './api'
import { useSearch } from './useSearch'
import { useToast } from './ToastContext'
import { DURATIONS, parseDuration } from './durations'

export default function AlbumSection() {
  const { query, setQuery, results, error } = useSearch((q) => api.albums(q), { debounceMs: 250 })
  const [duration, setDuration] = useState('once')
  const [busy, setBusy] = useState(null)
  const toast = useToast()

  async function play(a) {
    setBusy(`${a.id}:play`)
    try {
      const r = await api.playAlbum(a.id, a.name, parseDuration(duration))
      toast(`Playing "${a.name}" · ${r.queued} tracks`)
    } catch (e) {
      toast(`Couldn't play: ${e.message}`, 'error')
    } finally {
      setBusy(null)
    }
  }

  async function queueNext(a) {
    setBusy(`${a.id}:queue`)
    try {
      const r = await api.queueAlbumNext(a.id)
      toast(`Queued "${a.name}" next · ${r.queued} tracks`)
    } catch (e) {
      toast(`Couldn't queue: ${e.message}`, 'error')
    } finally {
      setBusy(null)
    }
  }

  return (
    <div>
      <div className="field-row">
        <input type="text" placeholder="Search albums…" value={query} onChange={(e) => setQuery(e.target.value)} />
      </div>
      <div className="field-row">
        <label className="inline-label" htmlFor="album-duration">
          "Play now" plays
        </label>
        <select id="album-duration" value={duration} onChange={(e) => setDuration(e.target.value)}>
          {DURATIONS.map((d) => (
            <option key={d.value} value={d.value}>
              {d.label}
            </option>
          ))}
        </select>
      </div>

      {error && <p className="empty">Couldn't load albums: {error}</p>}
      {!error && query && results.length === 0 && <p className="empty">No albums found.</p>}

      <ul className="result-list">
        {results.map((a) => (
          <li key={a.id} className="result-row">
            <span className="result-name">
              {a.name}
              <span className="result-sub">{a.artist}</span>
              <span className="result-count mono">{a.songCount}</span>
            </span>
            <span className="result-actions">
              <button className="btn-sm" disabled={busy === `${a.id}:queue`} onClick={() => queueNext(a)} title="Play right after the current track, don't disturb anything else">
                Queue next
              </button>
              <button className="btn-sm btn-primary" disabled={busy === `${a.id}:play`} onClick={() => play(a)}>
                Play now
              </button>
            </span>
          </li>
        ))}
      </ul>
    </div>
  )
}
