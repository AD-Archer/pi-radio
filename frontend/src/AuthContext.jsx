import { createContext, useContext, useEffect, useState } from 'react'
import { api } from './api'

const AuthCtx = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [setupNeeded, setSetupNeeded] = useState(false)
  const [loading, setLoading] = useState(true)

  async function refresh() {
    try {
      const s = await api.setupStatus()
      if (s.needed) {
        setSetupNeeded(true)
        setUser(null)
        return
      }
      setSetupNeeded(false)
      const r = await api.me()
      setUser(r.user)
    } catch {
      setUser(null)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    refresh()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  async function login(username, password) {
    const user = await api.login(username, password)
    setUser(user)
  }

  async function completeSetup(username, password) {
    const user = await api.setupAdmin(username, password)
    setSetupNeeded(false)
    setUser(user)
  }

  async function logout() {
    await api.logout()
    setUser(null)
  }

  return (
    <AuthCtx.Provider value={{ user, loading, setupNeeded, login, logout, completeSetup }}>
      {children}
    </AuthCtx.Provider>
  )
}

export function useAuth() {
  return useContext(AuthCtx)
}
