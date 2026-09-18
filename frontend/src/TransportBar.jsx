import { api } from './api'
import { useStatus } from './StatusContext'
import { useToast } from './ToastContext'
import { IconPause, IconPlayFilled, IconSkip } from './Icons'

export default function TransportBar() {
  const { status, refresh } = useStatus()
  const toast = useToast()
  const playing = status?.playback_state === 'playing'

  async function togglePlay() {
    try {
      if (playing) {
        await api.pause()
      } else {
        await api.resume()
      }
      refresh()
    } catch (e) {
      toast(`Couldn't ${playing ? 'pause' : 'resume'}: ${e.message}`, 'error')
    }
  }

  async function skip() {
    try {
      await api.skip()
      toast('Skipped')
      refresh()
    } catch (e) {
      toast(`Couldn't skip: ${e.message}`, 'error')
    }
  }

  return (
    <div className="transport-bar">
      <button className="transport-btn transport-btn-primary" onClick={togglePlay} aria-label={playing ? 'Pause' : 'Play'}>
        {playing ? <IconPause /> : <IconPlayFilled />}
      </button>
      <button className="transport-btn" onClick={skip} aria-label="Skip">
        <IconSkip />
      </button>
    </div>
  )
}
