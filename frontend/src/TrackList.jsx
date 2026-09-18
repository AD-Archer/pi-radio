import { useState } from 'react'
import { api } from './api'
import { useToast } from './ToastContext'

/** Shared list of songs with "Play now" (interrupts) / "Queue next"
 * (doesn't interrupt) actions - used by search results and Favorites. */
export default function TrackList({ tracks, emptyMessage }) {
  const [busy, setBusy] = useState(null)
  const toast = useToast()

  async function playNow(t) {
    setBusy(`${t.uri}:play`)
    try {
      await api.playSongNow(t.uri)
      toast(`Playing "${t.name}" now`)
    } catch (e) {
      toast(`Couldn't play: ${e.message}`, 'error')
    } finally {
      setBusy(null)
    }
  }

  async function queueNext(t) {
    setBusy(`${t.uri}:queue`)
    try {
      await api.queueSongNext(t.uri)
      toast(`"${t.name}" will play next`)
    } catch (e) {
      toast(`Couldn't queue: ${e.message}`, 'error')
    } finally {
      setBusy(null)
    }
  }

  if (tracks.length === 0 && emptyMessage) {
    return <p className="empty">{emptyMessage}</p>
  }

  return (
    <ul className="result-list">
      {tracks.map((t) => (
        <li key={t.uri} className="result-row">
          <span className="result-name">
            {t.name}
            <span className="result-sub">{t.artist}</span>
          </span>
          <span className="result-actions">
            <button className="btn-sm" disabled={busy === `${t.uri}:queue`} onClick={() => queueNext(t)} title="Play right after the current track">
              Queue next
            </button>
            <button className="btn-sm btn-primary" disabled={busy === `${t.uri}:play`} onClick={() => playNow(t)}>
              Play now
            </button>
          </span>
        </li>
      ))}
    </ul>
  )
}
