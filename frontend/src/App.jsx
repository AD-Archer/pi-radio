import { BrowserRouter, Route, Routes } from 'react-router-dom'
import { ToastProvider } from './ToastContext'
import { StatusProvider } from './StatusContext'
import Layout from './Layout'
import MainMenu from './MainMenu'
import NowPlayingScreen from './NowPlayingScreen'
import PlaySection from './PlaySection'
import SongSection from './SongSection'
import Favorites from './Favorites'
import Schedule from './Schedule'
import ManagePlaylists from './ManagePlaylists'
import './panels.css'

export default function App() {
  return (
    <StatusProvider>
      <ToastProvider>
        <BrowserRouter>
          <Routes>
            <Route element={<Layout />}>
              <Route path="/" element={<MainMenu />} />
              <Route path="/nowplaying" element={<NowPlayingScreen />} />
              <Route path="/playlists" element={<PlaySection />} />
              <Route path="/songs" element={<SongSection />} />
              <Route path="/favorites" element={<Favorites />} />
              <Route path="/schedule" element={<Schedule />} />
              <Route path="/rotation" element={<ManagePlaylists />} />
            </Route>
          </Routes>
        </BrowserRouter>
      </ToastProvider>
    </StatusProvider>
  )
}
