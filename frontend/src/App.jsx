import { useState } from 'react'
import { ToastProvider } from './ToastContext'
import { StatusProvider, useStatus } from './StatusContext'
import TitleBar from './TitleBar'
import MainMenu from './MainMenu'
import NowPlayingScreen from './NowPlayingScreen'
import PlaySection from './PlaySection'
import SongSection from './SongSection'
import Favorites from './Favorites'
import Schedule from './Schedule'
import ManagePlaylists from './ManagePlaylists'
import './panels.css'

const TITLES = {
  nowplaying: 'Now Playing',
  playlists: 'Playlists',
  songs: 'Songs',
  favorites: 'Favorites',
  schedule: 'Schedule',
  rotation: 'Rotation',
}

function Screen({ view }) {
  if (view === 'nowplaying') return <NowPlayingScreen />
  if (view === 'playlists') return <PlaySection />
  if (view === 'songs') return <SongSection />
  if (view === 'favorites') return <Favorites />
  if (view === 'schedule') return <Schedule />
  if (view === 'rotation') return <ManagePlaylists />
  return null
}

function Shell() {
  const [view, setView] = useState(null)
  const { status } = useStatus()

  return (
    <>
      <TitleBar title={view ? TITLES[view] : 'Radio'} onBack={view ? () => setView(null) : null} live={status?.playback_state === 'playing'} />
      <div className="content">{view ? <Screen view={view} /> : <MainMenu onSelect={setView} />}</div>
    </>
  )
}

export default function App() {
  return (
    <StatusProvider>
      <ToastProvider>
        <Shell />
      </ToastProvider>
    </StatusProvider>
  )
}
