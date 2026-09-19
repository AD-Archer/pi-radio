import { Link } from 'react-router-dom'
import { useStatus } from './StatusContext'
import { useAuth } from './AuthContext'

const ITEMS = [
  { path: '/nowplaying', label: 'Now Playing' },
  { path: '/playlists', label: 'Playlists' },
  { path: '/albums', label: 'Albums' },
  { path: '/songs', label: 'Songs' },
  { path: '/favorites', label: 'Favorites' },
]

const ADMIN_ITEMS = [
  { path: '/schedule', label: 'Schedule' },
  { path: '/rotation', label: 'Rotation' },
  { path: '/users', label: 'People' },
  { path: '/activity', label: 'Activity' },
]

export default function MainMenu() {
  const { status } = useStatus()
  const { user, logout } = useAuth()
  const track = status?.current_track
  const items = user.role === 'admin' ? [...ITEMS, ...ADMIN_ITEMS] : ITEMS

  return (
    <>
      <div className="account-line">
        Signed in as {user.username}
        <span className="role-badge">{user.role}</span>
      </div>
      <ul className="menu-list">
        {items.map((item) => (
          <li key={item.path}>
            <Link className="menu-row" to={item.path}>
              <span className="menu-row-text">
                <span className="menu-row-label">{item.label}</span>
                {item.path === '/nowplaying' && track && (
                  <span className="menu-row-sub">
                    {track.name}
                    {track.artists?.length ? ` by ${track.artists.map((a) => a.name).join(', ')}` : ''}
                  </span>
                )}
              </span>
              <span className="menu-chevron">›</span>
            </Link>
          </li>
        ))}
        <li>
          <button className="menu-row" onClick={logout}>
            <span className="menu-row-text">
              <span className="menu-row-label">Log out</span>
            </span>
          </button>
        </li>
      </ul>
    </>
  )
}
