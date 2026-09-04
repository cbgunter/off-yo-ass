import { useEffect, useState } from 'react'
import { api } from '@/lib/api'

const VAPID_PUBLIC_KEY = import.meta.env.VITE_VAPID_PUBLIC_KEY as string | undefined

function urlBase64ToUint8Array(base64: string): Uint8Array<ArrayBuffer> {
  const padding = '='.repeat((4 - (base64.length % 4)) % 4)
  const base64Safe = (base64 + padding).replace(/-/g, '+').replace(/_/g, '/')
  const raw = atob(base64Safe)
  // Uint8Array.from(...) infers Uint8Array<ArrayBufferLike>, which
  // PushManager.subscribe's BufferSource param rejects under TS 5.7's
  // stricter typed-array generics — building the buffer explicitly keeps
  // the type as the concrete ArrayBuffer it needs.
  const bytes = new Uint8Array(new ArrayBuffer(raw.length))
  for (let i = 0; i < raw.length; i++) {
    bytes[i] = raw.charCodeAt(i)
  }
  return bytes
}

type Status = 'checking' | 'unsupported' | 'denied' | 'subscribed' | 'available' | 'error'

/**
 * The opt-in for stale-source pushes. Lives on the Sources screen — that's
 * where you'd notice something's actually stale.
 */
export function PushPermission() {
  const [status, setStatus] = useState<Status>('checking')

  useEffect(() => {
    if (!('serviceWorker' in navigator) || !('PushManager' in window) || !VAPID_PUBLIC_KEY) {
      setStatus('unsupported')
      return
    }
    if (Notification.permission === 'denied') {
      setStatus('denied')
      return
    }
    navigator.serviceWorker.ready
      .then((registration) => registration.pushManager.getSubscription())
      .then((sub) => setStatus(sub ? 'subscribed' : 'available'))
      .catch(() => setStatus('error'))
  }, [])

  const enable = async () => {
    try {
      const permission = await Notification.requestPermission()
      if (permission !== 'granted') {
        setStatus('denied')
        return
      }
      const registration = await navigator.serviceWorker.ready
      const subscription = await registration.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: urlBase64ToUint8Array(VAPID_PUBLIC_KEY!),
      })
      await api.post('/push/subscribe', { subscription: subscription.toJSON() })
      setStatus('subscribed')
    } catch {
      setStatus('error')
    }
  }

  if (status === 'checking' || status === 'unsupported') return null

  if (status === 'subscribed') {
    return <p className="empty-state">Notifications on.</p>
  }

  if (status === 'denied') {
    return (
      <p className="empty-state">
        Notifications blocked. Re-enable them in your browser's site settings.
      </p>
    )
  }

  return (
    <div className="stack">
      <p className="body-text">Get a push when a source goes stale.</p>
      <button className="btn btn-primary" onClick={() => void enable()}>
        Enable notifications
      </button>
      {status === 'error' && <p className="empty-state">Could not enable notifications.</p>}
    </div>
  )
}
