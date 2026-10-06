import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vitest/config'
import { VitePWA } from 'vite-plugin-pwa'

const API = process.env.KCALIA_API ?? 'http://127.0.0.1:8765'

const pkg = JSON.parse(readFileSync(fileURLToPath(new URL('./package.json', import.meta.url)), 'utf8')) as { version: string }

export default defineConfig({
  define: {
    __APP_VERSION__: JSON.stringify(pkg.version),
    __REPO_URL__: JSON.stringify('https://github.com/Alvaro-Rovira/kcalia'),
  },
  resolve: { alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) } },
  plugins: [
    react(),
    tailwindcss(),
    VitePWA({
      // "prompt": la versión nueva espera a que el usuario pulse "Actualizar".
      registerType: 'prompt',
      injectRegister: false,
      includeAssets: ['favicon.svg', 'favicon-32.png', 'apple-touch-icon.png', 'theme.js', 'push-sw.js'],
      manifest: {
        id: '/',
        name: 'Kcalia',
        short_name: 'Kcalia',
        description: 'Calorías y macros con calma: apunta lo que comes en una frase, una foto o un audio.',
        lang: 'es-ES',
        dir: 'ltr',
        start_url: '/',
        scope: '/',
        display: 'standalone',
        orientation: 'portrait',
        background_color: '#0b0c0e',
        theme_color: '#0b0c0e',
        categories: ['health', 'fitness', 'food'],
        icons: [
          { src: '/icons/icon-192.png', sizes: '192x192', type: 'image/png', purpose: 'any' },
          { src: '/icons/icon-512.png', sizes: '512x512', type: 'image/png', purpose: 'any' },
          { src: '/icons/maskable-192.png', sizes: '192x192', type: 'image/png', purpose: 'maskable' },
          { src: '/icons/maskable-512.png', sizes: '512x512', type: 'image/png', purpose: 'maskable' },
        ],
        shortcuts: [
          { name: 'Añadir comida', short_name: 'Añadir', url: '/?nueva=1', icons: [{ src: '/icons/shortcut-add.png', sizes: '96x96', type: 'image/png' }] },
          { name: 'Apuntar peso', short_name: 'Peso', url: '/peso', icons: [{ src: '/icons/shortcut-weight.png', sizes: '96x96', type: 'image/png' }] },
        ],
      },
      workbox: {
        globPatterns: ['**/*.{js,css,html,svg,woff2}', 'icons/icon-*.png', 'favicon-32.png', 'apple-touch-icon.png'],
        navigateFallback: '/index.html',
        navigateFallbackDenylist: [/^\/api\//],
        // Recibir y abrir las notificaciones (recordatorios y avisos al admin).
        importScripts: ['/push-sw.js'],
        cleanupOutdatedCaches: true,
        // El lector de códigos de respaldo (iPhone) no va en la precarga: se guarda la primera vez que se usa.
        runtimeCaching: [{ urlPattern: /\/assets\/.*\.wasm$/, handler: 'CacheFirst', options: { cacheName: 'kcalia-wasm', expiration: { maxEntries: 2 } } }],
      },
    }),
  ],
  server: { port: 5173, proxy: { '/api': { target: API, changeOrigin: false } } },
  build: {
    target: 'es2022',
    sourcemap: false,
    // Sin manualChunks a propósito: forzar un chunk "charts" lo convertía en dependencia común de todas las
    // pantallas y se descargaba (400 KB) en Hoy, que no lo usa. Las páginas ya se cargan con import() dinámico.
  },
  test: { environment: 'node', include: ['src/**/*.test.ts'] },
})
