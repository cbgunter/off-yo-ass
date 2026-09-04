/// <reference lib="webworker" />

import { ExpirationPlugin } from 'workbox-expiration'
import { createHandlerBoundToURL, precacheAndRoute } from 'workbox-precaching'
import { NavigationRoute, registerRoute } from 'workbox-routing'
import { CacheFirst } from 'workbox-strategies'

declare let self: ServiceWorkerGlobalScope

// Same offline-shell caching the phase-0 generateSW config had, hand-built
// instead of config-driven — injectManifest has no equivalent of
// generateSW's `workbox: {...}` options, and injectManifest is what's
// needed here for the custom `push` handler below.
precacheAndRoute(self.__WB_MANIFEST)

// A direct navigation to e.g. /sources while offline has to fall back to
// the cached app shell — precacheAndRoute alone only serves exact
// precached URLs.
registerRoute(new NavigationRoute(createHandlerBoundToURL('/index.html')))

registerRoute(
  ({ url }) => url.hostname === 'fonts.googleapis.com' || url.hostname === 'fonts.gstatic.com',
  new CacheFirst({
    cacheName: 'google-fonts',
    plugins: [new ExpirationPlugin({ maxEntries: 8, maxAgeSeconds: 60 * 60 * 24 * 365 })],
  }),
)

type PushPayload = { title: string; body: string }

self.addEventListener('push', (event: PushEvent) => {
  if (!event.data) return
  const { title, body } = event.data.json() as PushPayload
  event.waitUntil(
    self.registration.showNotification(title, {
      body,
      icon: '/icons/icon-192.png',
    }),
  )
})

self.addEventListener('notificationclick', (event: NotificationEvent) => {
  event.notification.close()
  event.waitUntil(
    self.clients.matchAll({ type: 'window' }).then((clientsList) => {
      for (const client of clientsList) {
        if ('focus' in client) return (client as WindowClient).focus()
      }
      return self.clients.openWindow('/')
    }),
  )
})
