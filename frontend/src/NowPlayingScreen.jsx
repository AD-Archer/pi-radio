import { useEffect, useRef } from 'react'
import { api } from './api'
import { useToast } from './ToastContext'
import { useStatus } from './StatusContext'
import { IconChevronDown, IconChevronUp, IconClose, IconStar } from './Icons'
import './NowPlaying.css'

function modeLine(status) {
  if (status.override) {
    const mins = status.seconds_left != null ? `${Math.round(status.seconds_left / 60)} min left` : 'until changed'
    const detail = status.override.once ? 'playing once' : `on loop · ${mins}`
    return { text: `"${status.override.name}" · ${detail}`, canCancel: true }
  }
  if (status.active_schedule) {
    return { text: `Schedule: "${status.active_schedule.name}" since ${status.active_schedule.time}`, canCancel: false }
  }
  if (status.default_state) {
    return { text: `In rotation: "${status.default_state.name}"`, canCancel: false }
  }
  return { text: 'Nothing queued', canCancel: false }
}

export default function NowPlayingScreen() {
  const { status, queue, refresh } = useStatus()
  const toast = useToast()
  const cardRef = useRef(null)
  const didInitialScroll = useRef(false)

  useEffect(() => {
    if (!didInitialScroll.current && cardRef.current) {
      cardRef.current.scrollIntoView({ block: 'start' })
      didInitialScroll.current = true
    }
  }, [queue])

  async function cancelOverride() {
    try {
      const r = await api.cancelOverride()
      toast(`Back to rotation · "${r.name}"`)
      refresh()
    } catch (e) {
      toast(`Couldn't switch back: ${e.message}`, 'error')
    }
  }

  async function removeFromQueue(tlid, e) {
    e.stopPropagation()
    try {
      await api.removeFromQueue(tlid)
      refresh()
    } catch (err) {
      toast(`Couldn't remove: ${err.message}`, 'error')
    }
  }

  async function jumpTo(t) {
    try {
      await api.playFromQueue(t.tlid)
      toast(`Skipping to "${t.name}"`)
      refresh()
    } catch (e) {
      toast(`Couldn't skip there: ${e.message}`, 'error')
    }
  }

  async function moveTrack(tlid, direction, e) {
    e.stopPropagation()
    try {
      const r = await api.moveInQueue(tlid, direction)
      if (!r.ok) {
        toast("Can't move it any further that way", 'error')
      }
      refresh()
    } catch (err) {
      toast(`Couldn't reorder: ${err.message}`, 'error')
    }
  }

  async function toggleStar() {
    try {
      const next = !status.current_track_starred
      await api.setStarred(status.current_track.uri, next)
      toast(next ? 'Added to favorites' : 'Removed from favorites')
      refresh()
    } catch (e) {
      toast(`Couldn't update favorite: ${e.message}`, 'error')
    }
  }

  if (!status) {
    return <p className="empty">Loading…</p>
  }

  const track = status.current_track
  const playing = status.playback_state === 'playing'
  const mode = modeLine(status)

  return (
    <div className="onair">
      {queue.history.length > 0 && (
        <>
          <p className="section-title">Recently played</p>
          <ol className="cuesheet cuesheet-history">
            {queue.history.map((t) => (
              <li key={t.tlid} className="cuesheet-row" onClick={() => jumpTo(t)} title="Play this again">
                <span className="cuesheet-track">
                  <span className="cuesheet-name">{t.name}</span>
                  <span className="cuesheet-artist">{t.artist}</span>
                </span>
              </li>
            ))}
          </ol>
        </>
      )}

      <div className="nowplaying-card" ref={cardRef}>
        <div className="onair-header">
          <span className="onair-badge">{playing ? 'playing' : 'paused'}</span>
          {track && (
            <button className="btn-icon star-btn" onClick={toggleStar} aria-label={status.current_track_starred ? 'Remove from favorites' : 'Add to favorites'}>
              <IconStar filled={status.current_track_starred} />
            </button>
          )}
        </div>

        <h1 className="onair-title">{track ? track.name : 'Nothing playing'}</h1>
        <div className="onair-artist">{track?.artists?.length ? track.artists.map((a) => a.name).join(', ') : ' '}</div>

        <div className="onair-mode">
          {mode.text}
          {mode.canCancel && (
            <button className="link" onClick={cancelOverride}>
              back to rotation
            </button>
          )}
        </div>
      </div>

      {queue.upcoming.length > 0 && (
        <>
          <p className="section-title">Up next</p>
          <ol className="cuesheet">
            {queue.upcoming.map((t, i) => (
              <li key={t.tlid} className="cuesheet-row" onClick={() => jumpTo(t)} title="Skip to this track">
                <span className="cuesheet-num mono">{i + 1}</span>
                <span className="cuesheet-track">
                  <span className="cuesheet-name">{t.name}</span>
                  <span className="cuesheet-artist">{t.artist}</span>
                </span>
                <span className="cuesheet-move">
                  <button className="btn-icon btn-icon-tiny" onClick={(e) => moveTrack(t.tlid, 'up', e)} title="Move up" aria-label="Move up">
                    <IconChevronUp />
                  </button>
                  <button className="btn-icon btn-icon-tiny" onClick={(e) => moveTrack(t.tlid, 'down', e)} title="Move down" aria-label="Move down">
                    <IconChevronDown />
                  </button>
                </span>
                <button className="btn-icon" onClick={(e) => removeFromQueue(t.tlid, e)} title="Remove from queue" aria-label="Remove">
                  <IconClose />
                </button>
              </li>
            ))}
          </ol>
        </>
      )}
    </div>
  )
}
