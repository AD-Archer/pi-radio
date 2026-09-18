import { createContext, useContext, useEffect, useState } from 'react'
import { api } from './api'

const StatusCtx = createContext(null)

export function StatusProvider({ children }) {
  const [status, setStatus] = useState(null)
  const [queue, setQueue] = useState({ upcoming: [] })

  async function refresh() {
    try {
      const [s, q] = await Promise.all([api.status(), api.queue()])
      setStatus(s)
      setQueue(q)
    } catch {
      // transient network hiccup - next poll catches up
    }
  }

  useEffect(() => {
    refresh()
    const id = setInterval(refresh, 4000)
    return () => clearInterval(id)
  }, [])

  return <StatusCtx.Provider value={{ status, queue, refresh }}>{children}</StatusCtx.Provider>
}

export function useStatus() {
  return useContext(StatusCtx)
}
