import { useEffect, useRef, useState } from 'react'

/** Debounced search against an async searchFn(query) -> results[]. */
export function useSearch(searchFn, { debounceMs = 300, minLength = 0 } = {}) {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const timer = useRef(null)
  const requestId = useRef(0)

  useEffect(() => {
    clearTimeout(timer.current)
    if (query.length < minLength) {
      setResults([])
      setError(null)
      return
    }
    setLoading(true)
    timer.current = setTimeout(async () => {
      const id = ++requestId.current
      try {
        const r = await searchFn(query)
        if (id === requestId.current) {
          setResults(r)
          setError(null)
        }
      } catch (e) {
        if (id === requestId.current) setError(e.message)
      } finally {
        if (id === requestId.current) setLoading(false)
      }
    }, debounceMs)
    return () => clearTimeout(timer.current)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [query])

  return { query, setQuery, results, loading, error }
}
