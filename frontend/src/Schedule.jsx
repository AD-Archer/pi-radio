import { useEffect, useState } from 'react'
import { api } from './api'
import { useSearch } from './useSearch'
import { useToast } from './ToastContext'
import { IconClose } from './Icons'

export default function Schedule() {
  const { query, setQuery, results } = useSearch((q) => api.playlists(q), { debounceMs: 250 })
  const [time, setTime] = useState('')
  const [selected, setSelected] = useState(null)
  const [schedules, setSchedules] = useState([])
  const toast = useToast()

  async function load() {
    try {
      setSchedules(await api.schedules())
    } catch (e) {
      toast(`Couldn't load schedule: ${e.message}`, 'error')
    }
  }

  useEffect(() => {
    load()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  async function add() {
    if (!time || !selected) {
      toast('Pick a time and a playlist first', 'error')
      return
    }
    try {
      await api.addSchedule(selected.id, selected.name, time)
      toast('Added to the schedule')
      setSelected(null)
      setQuery('')
      load()
    } catch (e) {
      toast(`Couldn't add: ${e.message}`, 'error')
    }
  }

  async function remove(id) {
    try {
      await api.removeSchedule(id)
      load()
    } catch (e) {
      toast(`Couldn't remove: ${e.message}`, 'error')
    }
  }

  return (
    <div>
      <p className="section-title">Every day, at a fixed time</p>
      <div className="field-row">
        <input type="time" className="mono" style={{ flex: '0 0 8rem' }} value={time} onChange={(e) => setTime(e.target.value)} />
        <input type="text" placeholder="Search a playlist to schedule…" value={query} onChange={(e) => setQuery(e.target.value)} />
      </div>

      <ul className="result-list">
        {results.map((p) => (
          <li key={p.id} className="result-row">
            <span className="result-name">
              {p.name}
              <span className="result-count mono">{p.songCount}</span>
            </span>
            <button className="btn-sm" onClick={() => setSelected(p)}>
              Select
            </button>
          </li>
        ))}
      </ul>

      {selected && (
        <div className="selected-chip">
          <span>
            Selected: <strong>{selected.name}</strong>
          </span>
          <button className="btn-sm btn-primary" onClick={add}>
            Add to schedule
          </button>
        </div>
      )}

      <ol className="schedule-list">
        {schedules.length === 0 && <p className="empty">No recurring schedule set — the rotation plays all day.</p>}
        {schedules.map((s) => (
          <li key={s.id} className="schedule-row">
            <span className="time-badge mono">{s.time}</span>
            <span className="result-name">{s.name}</span>
            <button className="btn-icon" onClick={() => remove(s.id)} aria-label="Remove from schedule">
              <IconClose />
            </button>
          </li>
        ))}
      </ol>
    </div>
  )
}
