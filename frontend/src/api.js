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
  me: () => request('/api/auth/me'),
  login: (username, password) => request('/api/auth/login', json({ username, password })),
  logout: () => request('/api/auth/logout', { method: 'POST' }),

  users: () => request('/api/admin/users'),
  createUser: (username, password, role) => request('/api/admin/users', json({ username, password, role })),
  setUserRole: (id, role) => request(`/api/admin/users/${id}`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ role }) }),
  deleteUser: (id) => request(`/api/admin/users/${id}`, { method: 'DELETE' }),
  generateToken: (id) => request(`/api/admin/users/${id}/token`, { method: 'POST' }),
  revokeToken: (id) => request(`/api/admin/users/${id}/token`, { method: 'DELETE' }),
  auditLog: () => request('/api/admin/audit-log'),

  status: () => request('/api/status'),
  queue: () => request('/api/queue'),
  skip: () => request('/api/skip', { method: 'POST' }),
  previous: () => request('/api/previous', { method: 'POST' }),
  pause: () => request('/api/pause', { method: 'POST' }),
  resume: () => request('/api/resume', { method: 'POST' }),
  removeFromQueue: (tlid) => request(`/api/queue/${tlid}`, { method: 'DELETE' }),
  playFromQueue: (tlid) => request(`/api/queue/${tlid}/play`, { method: 'POST' }),
  moveInQueue: (tlid, direction) => request(`/api/queue/${tlid}/move`, json({ direction })),
  setStarred: (uri, starred) =>
    request(`/api/favorites/${uri}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ starred }),
    }),

  playlists: (q) => request(`/api/playlists?q=${encodeURIComponent(q)}`),
  playPlaylist: (playlistId, name, { once, minutes } = {}) =>
    request('/api/play', json({ playlist_id: playlistId, name, once, minutes })),
  queuePlaylistNext: (playlistId) =>
    request('/api/queue-playlist-next', json({ playlist_id: playlistId })),
  cancelOverride: () => request('/api/cancel', { method: 'POST' }),

  albums: (q) => request(`/api/albums?q=${encodeURIComponent(q)}`),
  playAlbum: (albumId, name, { once, minutes } = {}) =>
    request('/api/play-album', json({ album_id: albumId, name, once, minutes })),
  queueAlbumNext: (albumId) => request('/api/queue-album-next', json({ album_id: albumId })),

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
