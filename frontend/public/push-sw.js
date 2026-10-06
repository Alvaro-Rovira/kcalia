/* Notificaciones de Kcalia. Se carga dentro del service worker generado (workbox.importScripts en vite.config.ts). */
self.addEventListener('push', (event) => {
  let data = {}
  try {
    data = event.data ? event.data.json() : {}
  } catch {
    data = { body: event.data ? event.data.text() : '' }
  }
  event.waitUntil(
    self.registration.showNotification(data.title || 'Kcalia', {
      body: data.body || '',
      icon: '/icons/icon-192.png',
      badge: '/favicon-32.png',
      tag: data.tag,
      data: { url: data.url || '/' },
    }),
  )
})

// Al tocar el aviso se abre la app (o se enfoca la que ya esté abierta) en la pantalla que corresponde.
self.addEventListener('notificationclick', (event) => {
  event.notification.close()
  const url = new URL((event.notification.data && event.notification.data.url) || '/', self.location.origin).href
  event.waitUntil(
    (async () => {
      const windows = await self.clients.matchAll({ type: 'window', includeUncontrolled: true })
      for (const client of windows) {
        if (client.url.startsWith(self.location.origin)) {
          await client.focus()
          if ('navigate' in client) await client.navigate(url)
          return
        }
      }
      await self.clients.openWindow(url)
    })(),
  )
})
