import { useEffect, useState } from 'react'
import { api } from './api'
import { useToast } from './ToastContext'

export default function ManagePlaylists() {
  const [playlists, setPlaylists] = useState([])
  const toast = useToast()

  async function load() {
    try {
      setPlaylists(await api.exclusions())
    } catch (e) {
      toast(`Couldn't load playlists: ${e.message}`, 'error')
    }
  }

  useEffect(() => {
    load()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  async function toggle(p) {
    const next = !p.excluded
    setPlaylists((list) => list.map((x) => (x.id === p.id ? { ...x, excluded: next } : x)))
    try {
      await api.setExclusion(p.id, next)
    } catch (e) {
      toast(`Couldn't update: ${e.message}`, 'error')
      load()
    }
  }

  return (
    <div>
      <p className="hint">Unchecked playlists are skipped by the random rotation. They still work for search-and-play and scheduling.</p>
      <ul className="result-list">
        {playlists.map((p) => (
          <li key={p.id} className="result-row">
            <label className="checkbox-row">
              <input type="checkbox" checked={!p.excluded} onChange={() => toggle(p)} />
              <span className="result-name">
                {p.name}
                <span className="result-count mono">{p.songCount}</span>
              </span>
            </label>
          </li>
        ))}
      </ul>
    </div>
  )
}
