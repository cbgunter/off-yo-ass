import { fileURLToPath, URL } from 'node:url'
import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'
import { VitePWA } from 'vite-plugin-pwa'

// https://vite.dev/config/
export default defineConfig({
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  plugins: [
    react(),
    VitePWA({
      // injectManifest, not the default generateSW: a custom `push`
      // event handler (web/src/sw.ts) needs a service worker source file
      // to add it to — generateSW has no hook for that.
      strategies: 'injectManifest',
      srcDir: 'src',
      filename: 'sw.ts',
      injectManifest: {
        globPatterns: ['**/*.{js,css,html,woff2}'],
      },
      registerType: 'autoUpdate',
      includeAssets: ['icons/apple-touch-icon.png'],
      manifest: {
        name: 'Off Yo Ass',
        short_name: 'Off Yo Ass',
        description: 'Get off your lazy ass.',
        start_url: '/',
        display: 'standalone',
        // Warm paper, per BRANDING.md — not white, matches the app shell.
        // theme_color must match index.html's <meta name="theme-color">, or
        // the installed PWA's status bar tints differently from the browser
        // tab. --clay is reserved for the prescription/primary action, never
        // chrome, so both are paper.
        background_color: '#F5F2EC',
        theme_color: '#F5F2EC',
        icons: [
          { src: '/icons/icon-192.png', sizes: '192x192', type: 'image/png', purpose: 'any' },
          { src: '/icons/icon-512.png', sizes: '512x512', type: 'image/png', purpose: 'any' },
          {
            src: '/icons/icon-512-maskable.png',
            sizes: '512x512',
            type: 'image/png',
            purpose: 'maskable',
          },
        ],
      },
    }),
  ],
  server: {
    proxy: {
      // Same-origin /api/* in production (CloudFront); mirror that locally
      // against the FastAPI dev server so no CORS handling is ever needed.
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    globals: false,
  },
})
