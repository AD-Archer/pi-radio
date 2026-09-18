async function request(path, opts) {
  const res = await fetch(path, opts)
  const data = await res.json().catch(() => ({}))
  if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`)
  return data
}

const json = (body) => ({
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(body),
})

export const api = {
  status: () => request('/api/status'),
  queue: () => request('/api/queue'),
  skip: () => request('/api/skip', { method: 'POST' }),
  pause: () => request('/api/pause', { method: 'POST' }),
  resume: () => request('/api/resume', { method: 'POST' }),
  removeFromQueue: (tlid) => request(`/api/queue/${tlid}`, { method: 'DELETE' }),
  playFromQueue: (tlid) => request(`/api/queue/${tlid}/play`, { method: 'POST' }),

  playlists: (q) => request(`/api/playlists?q=${encodeURIComponent(q)}`),
  playPlaylist: (playlistId, name, { once, minutes } = {}) =>
    request('/api/play', json({ playlist_id: playlistId, name, once, minutes })),
  queuePlaylistNext: (playlistId) =>
    request('/api/queue-playlist-next', json({ playlist_id: playlistId })),
  cancelOverride: () => request('/api/cancel', { method: 'POST' }),

  songs: (q) => request(`/api/songs?q=${encodeURIComponent(q)}`),
  playSongNow: (uri) => request('/api/play-song', json({ uri })),
  queueSongNext: (uri) => request('/api/queue-song', json({ uri })),
  favorites: () => request('/api/favorites'),

  schedules: () => request('/api/schedules'),
  addSchedule: (playlistId, name, time) =>
    request('/api/schedules', json({ playlist_id: playlistId, name, time })),
  removeSchedule: (id) => request(`/api/schedules/${id}`, { method: 'DELETE' }),

  exclusions: () => request('/api/exclusions'),
  setExclusion: (id, excluded) =>
    request(`/api/exclusions/${id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ excluded }),
    }),
}
