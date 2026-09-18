import { Link } from 'react-router-dom'
import { useStatus } from './StatusContext'

const ITEMS = [
  { path: '/nowplaying', label: 'Now Playing' },
  { path: '/playlists', label: 'Playlists' },
  { path: '/songs', label: 'Songs' },
  { path: '/favorites', label: 'Favorites' },
  { path: '/schedule', label: 'Schedule' },
  { path: '/rotation', label: 'Rotation' },
]

export default function MainMenu() {
  const { status } = useStatus()
  const track = status?.current_track

  return (
    <ul className="menu-list">
      {ITEMS.map((item) => (
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
    </ul>
  )
}
