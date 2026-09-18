import { useEffect, useState } from 'react'
import { api } from './api'
import { useToast } from './ToastContext'
import TrackList from './TrackList'

export default function Favorites() {
  const [tracks, setTracks] = useState(null)
  const [filter, setFilter] = useState('')
  const toast = useToast()

  useEffect(() => {
    api.favorites().then(setTracks).catch((e) => {
      toast(`Couldn't load favorites: ${e.message}`, 'error')
      setTracks([])
    })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  if (tracks === null) {
    return <p className="empty">Loading favorites…</p>
  }

  const q = filter.trim().toLowerCase()
  const shown = q ? tracks.filter((t) => t.name.toLowerCase().includes(q) || t.artist.toLowerCase().includes(q)) : tracks

  return (
    <div>
      <div className="field-row">
        <input type="text" placeholder="Filter favorites…" value={filter} onChange={(e) => setFilter(e.target.value)} />
      </div>
      <TrackList tracks={shown} emptyMessage={tracks.length === 0 ? 'No starred songs in Navidrome yet.' : 'No matches.'} />
    </div>
  )
}
