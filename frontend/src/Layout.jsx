import { Outlet, useLocation, useNavigate } from 'react-router-dom'
import TitleBar from './TitleBar'
import TransportBar from './TransportBar'
import { useStatus } from './StatusContext'

const TITLES = {
  '/': 'Radio',
  '/nowplaying': 'Now Playing',
  '/playlists': 'Playlists',
  '/songs': 'Songs',
  '/favorites': 'Favorites',
  '/schedule': 'Schedule',
  '/rotation': 'Rotation',
}

export default function Layout() {
  const location = useLocation()
  const navigate = useNavigate()
  const { status } = useStatus()
  const isRoot = location.pathname === '/'

  return (
    <>
      <TitleBar
        title={TITLES[location.pathname] || 'Radio'}
        onBack={isRoot ? null : () => navigate('/')}
        live={status?.playback_state === 'playing'}
      />
      <div className="content">
        <Outlet />
      </div>
      <TransportBar />
    </>
  )
}
