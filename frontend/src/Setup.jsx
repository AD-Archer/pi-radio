import { useState } from 'react'
import { useAuth } from './AuthContext'

export default function Setup() {
  const { completeSetup } = useAuth()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)

  async function submit(e) {
    e.preventDefault()
    if (password !== confirm) {
      setError('Passwords do not match')
      return
    }
    setBusy(true)
    setError(null)
    try {
      await completeSetup(username, password)
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="login-screen">
      <h1 className="login-title">Radio</h1>
      <p className="login-subtitle">No admin account exists yet. Create one to get started.</p>
      <form className="login-form" onSubmit={submit}>
        <input
          type="text"
          placeholder="Username"
          autoComplete="username"
          value={username}
          onChange={(e) => setUsername(e.target.value)}
        />
        <input
          type="password"
          placeholder="Password"
          autoComplete="new-password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />
        <input
          type="password"
          placeholder="Confirm password"
          autoComplete="new-password"
          value={confirm}
          onChange={(e) => setConfirm(e.target.value)}
        />
        {error && <p className="login-error">{error}</p>}
        <button className="btn-sm btn-primary login-submit" type="submit" disabled={busy}>
          Create admin account
        </button>
      </form>
    </div>
  )
}
