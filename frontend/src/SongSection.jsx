import { api } from './api'
import { useSearch } from './useSearch'
import TrackList from './TrackList'

export default function SongSection() {
  const { query, setQuery, results, loading, error } = useSearch((q) => api.songs(q), { debounceMs: 400, minLength: 1 })

  return (
    <div>
      <div className="field-row">
        <input type="text" placeholder="Search songs…" value={query} onChange={(e) => setQuery(e.target.value)} />
      </div>

      {loading && <p className="empty">Searching (can take a few seconds)…</p>}
      {error && <p className="empty">Search failed: {error}</p>}
      {!loading && !error && <TrackList tracks={results} emptyMessage={query ? 'No songs found.' : null} />}
    </div>
  )
}
