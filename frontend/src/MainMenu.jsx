import { useStatus } from './StatusContext'

const ITEMS = [
  { id: 'nowplaying', label: 'Now Playing' },
  { id: 'playlists', label: 'Playlists' },
  { id: 'songs', label: 'Songs' },
  { id: 'favorites', label: 'Favorites' },
  { id: 'schedule', label: 'Schedule' },
  { id: 'rotation', label: 'Rotation' },
]

export default function MainMenu({ onSelect }) {
  const { status } = useStatus()
  const track = status?.current_track

  return (
    <ul className="menu-list">
      {ITEMS.map((item) => (
        <li key={item.id}>
          <button className="menu-row" onClick={() => onSelect(item.id)}>
            <span className="menu-row-text">
              <span className="menu-row-label">{item.label}</span>
              {item.id === 'nowplaying' && track && (
                <span className="menu-row-sub">
                  {track.name}
                  {track.artists?.length ? ` by ${track.artists.map((a) => a.name).join(', ')}` : ''}
                </span>
              )}
            </span>
            <span className="menu-chevron">›</span>
          </button>
        </li>
      ))}
    </ul>
  )
}
