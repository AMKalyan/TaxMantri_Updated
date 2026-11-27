import { useEffect, useState } from 'react'
import { API_BASE } from '../../api/client.js'

/**
 * The free Render instance sleeps after ~15 minutes idle and takes 30-60 s to
 * wake. Ping /health on load; if it is slow, tell the visitor what is happening
 * instead of letting the first request look broken.
 */
export default function ServerWakeBanner() {
  const [state, setState] = useState('checking') // checking | waking | ready | down

  useEffect(() => {
    let cancelled = false
    const slowTimer = setTimeout(() => !cancelled && setState((s) => (s === 'checking' ? 'waking' : s)), 2500)
    const started = Date.now()

    async function ping() {
      while (!cancelled && Date.now() - started < 120000) {
        try {
          const r = await fetch(`${API_BASE}/health`, { cache: 'no-store' })
          if (r.ok) {
            if (!cancelled) setState('ready')
            return
          }
        } catch {
          /* server still starting */
        }
        await new Promise((res) => setTimeout(res, 3000))
      }
      if (!cancelled) setState('down')
    }
    ping()
    return () => {
      cancelled = true
      clearTimeout(slowTimer)
    }
  }, [])

  if (state === 'checking' || state === 'ready') return null

  return (
    <div
      role="status"
      aria-live="polite"
      className={`fixed bottom-20 left-1/2 z-50 w-[calc(100%-2rem)] max-w-md -translate-x-1/2 rounded-xl border px-4 py-3 text-sm shadow-card sm:bottom-4 ${
        state === 'down' ? 'border-red-200 bg-red-50 text-red-800' : 'border-amber-200 bg-amber-50 text-amber-900'
      }`}
    >
      {state === 'waking' ? (
        <span className="flex items-center gap-2">
          <span className="h-3 w-3 shrink-0 animate-spin rounded-full border-2 border-amber-600 border-t-transparent" />
          Waking up the server — free hosting sleeps when idle. This takes about 30–60 seconds.
        </span>
      ) : (
        <span>The server isn't responding right now. Please refresh in a minute.</span>
      )}
    </div>
  )
}
