import { useEffect, useState } from 'react'
import { api } from './api'
import { useAuth } from './AuthContext'
import { useToast } from './ToastContext'

export default function Users() {
  const { user: me } = useAuth()
  const [users, setUsers] = useState(null)
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [role, setRole] = useState('member')
  const [tokens, setTokens] = useState({})
  const toast = useToast()

  async function load() {
    try {
      setUsers(await api.users())
    } catch (e) {
      toast(`Couldn't load users: ${e.message}`, 'error')
    }
  }

  useEffect(() => {
    load()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  async function createUser(e) {
    e.preventDefault()
    if (!username || !password) return
    try {
      await api.createUser(username, password, role)
      toast(`Created ${role} "${username}"`)
      setUsername('')
      setPassword('')
      setRole('member')
      load()
    } catch (err) {
      toast(`Couldn't create user: ${err.message}`, 'error')
    }
  }

  async function toggleRole(u) {
    const next = u.role === 'admin' ? 'member' : 'admin'
    try {
      await api.setUserRole(u.id, next)
      load()
    } catch (e) {
      toast(`Couldn't change role: ${e.message}`, 'error')
    }
  }

  async function removeUser(u) {
    try {
      await api.deleteUser(u.id)
      toast(`Removed "${u.username}"`)
      load()
    } catch (e) {
      toast(`Couldn't remove: ${e.message}`, 'error')
    }
  }

  async function makeToken(u) {
    try {
      const r = await api.generateToken(u.id)
      setTokens((t) => ({ ...t, [u.id]: r.token }))
    } catch (e) {
      toast(`Couldn't generate token: ${e.message}`, 'error')
    }
  }

  async function revokeToken(u) {
    try {
      await api.revokeToken(u.id)
      setTokens((t) => ({ ...t, [u.id]: null }))
      toast(`Revoked token for "${u.username}"`)
    } catch (e) {
      toast(`Couldn't revoke: ${e.message}`, 'error')
    }
  }

  return (
    <div>
      <p className="section-title">Add a person</p>
      <form onSubmit={createUser}>
        <div className="field-row">
          <input type="text" placeholder="Username" value={username} onChange={(e) => setUsername(e.target.value)} />
        </div>
        <div className="field-row">
          <input type="password" placeholder="Password" value={password} onChange={(e) => setPassword(e.target.value)} />
        </div>
        <div className="field-row">
          <select value={role} onChange={(e) => setRole(e.target.value)}>
            <option value="member">Member - playback &amp; queue</option>
            <option value="admin">Admin - full control</option>
          </select>
          <button className="btn-sm btn-primary" type="submit">
            Create
          </button>
        </div>
      </form>

      <p className="section-title">People</p>
      {users === null && <p className="empty">Loading…</p>}
      <ul className="result-list">
        {users?.map((u) => (
          <li key={u.id} className="result-row user-row">
            <div className="user-row-inner">
              <span className="result-name">
                {u.username}
                {u.id === me.id && ' (you)'}
                <span className="role-badge">{u.role}</span>
              </span>
              <span className="result-actions">
                <button className="btn-sm" onClick={() => toggleRole(u)} disabled={u.id === me.id}>
                  Make {u.role === 'admin' ? 'member' : 'admin'}
                </button>
                <button className="btn-sm" onClick={() => makeToken(u)}>
                  API token
                </button>
                <button className="btn-sm" onClick={() => removeUser(u)} disabled={u.id === me.id}>
                  Remove
                </button>
              </span>
            </div>
            {tokens[u.id] && (
              <div className="token-box mono">
                {tokens[u.id]}
                <button className="btn-sm token-revoke" onClick={() => revokeToken(u)}>
                  Revoke
                </button>
              </div>
            )}
          </li>
        ))}
      </ul>
    </div>
  )
}
