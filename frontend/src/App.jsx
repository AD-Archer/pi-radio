import { BrowserRouter, Route, Routes } from 'react-router-dom'
import { AuthProvider, useAuth } from './AuthContext'
import { ToastProvider } from './ToastContext'
import { StatusProvider } from './StatusContext'
import Login from './Login'
import Setup from './Setup'
import Layout from './Layout'
import MainMenu from './MainMenu'
import NowPlayingScreen from './NowPlayingScreen'
import PlaySection from './PlaySection'
import AlbumSection from './AlbumSection'
import SongSection from './SongSection'
import Favorites from './Favorites'
import Schedule from './Schedule'
import ManagePlaylists from './ManagePlaylists'
import Users from './Users'
import Activity from './Activity'
import './panels.css'

function AuthedApp() {
  const { user, loading, setupNeeded } = useAuth()

  if (loading) return null
  if (setupNeeded) return <Setup />
  if (!user) return <Login />

  return (
    <StatusProvider>
      <ToastProvider>
        <BrowserRouter>
          <Routes>
            <Route element={<Layout />}>
              <Route path="/" element={<MainMenu />} />
              <Route path="/nowplaying" element={<NowPlayingScreen />} />
              <Route path="/playlists" element={<PlaySection />} />
              <Route path="/albums" element={<AlbumSection />} />
              <Route path="/songs" element={<SongSection />} />
              <Route path="/favorites" element={<Favorites />} />
              {user.role === 'admin' && <Route path="/schedule" element={<Schedule />} />}
              {user.role === 'admin' && <Route path="/rotation" element={<ManagePlaylists />} />}
              {user.role === 'admin' && <Route path="/users" element={<Users />} />}
              {user.role === 'admin' && <Route path="/activity" element={<Activity />} />}
            </Route>
          </Routes>
        </BrowserRouter>
      </ToastProvider>
    </StatusProvider>
  )
}

export default function App() {
  return (
    <AuthProvider>
      <AuthedApp />
    </AuthProvider>
  )
}
