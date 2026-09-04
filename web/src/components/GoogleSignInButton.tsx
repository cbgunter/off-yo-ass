import { useEffect, useRef, useState } from 'react'
import { api } from '@/lib/api'
import { useAuth } from '@/lib/auth'

const GSI_SRC = 'https://accounts.google.com/gsi/client'
const CLIENT_ID = import.meta.env.VITE_GOOGLE_CLIENT_ID as string | undefined

function loadScript(src: string): Promise<void> {
  return new Promise((resolve, reject) => {
    if (document.querySelector(`script[src="${src}"]`)) {
      resolve()
      return
    }
    const script = document.createElement('script')
    script.src = src
    script.async = true
    script.defer = true
    script.onload = () => resolve()
    script.onerror = () => reject(new Error(`failed to load ${src}`))
    document.head.appendChild(script)
  })
}

export function GoogleSignInButton() {
  const containerRef = useRef<HTMLDivElement>(null)
  const { refresh } = useAuth()
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!CLIENT_ID) {
      setError('Google client ID is not configured.')
      return
    }

    let cancelled = false

    loadScript(GSI_SRC)
      .then(() => {
        if (cancelled || !window.google || !containerRef.current) return

        window.google.accounts.id.initialize({
          client_id: CLIENT_ID,
          auto_select: false,
          callback: async (response) => {
            try {
              await api.post('/auth/google', { id_token: response.credential })
              await refresh()
            } catch {
              setError('Sign-in was rejected. This app is locked to one account.')
            }
          },
        })

        window.google.accounts.id.renderButton(containerRef.current, {
          type: 'standard',
          theme: 'outline',
          size: 'large',
          text: 'signin_with',
          shape: 'rectangular',
          width: 320,
        })
      })
      .catch(() => setError('Could not reach Google. Check your connection.'))

    return () => {
      cancelled = true
    }
  }, [refresh])

  return (
    <div className="stack">
      <div ref={containerRef} />
      {error && <p className="body-text">{error}</p>}
    </div>
  )
}
