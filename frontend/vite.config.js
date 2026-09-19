import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'
import { VitePWA } from 'vite-plugin-pwa'

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      registerType: 'autoUpdate',
      includeAssets: ['favicon.png', 'apple-touch-icon.png'],
      manifest: {
        name: 'Radio',
        short_name: 'Radio',
        description: 'Navidrome radio control',
        start_url: '/',
        display: 'standalone',
        background_color: '#f4f4f2',
        theme_color: '#1c5fd6',
        icons: [
          { src: 'icon-192.png', sizes: '192x192', type: 'image/png' },
          { src: 'icon-512.png', sizes: '512x512', type: 'image/png' },
          { src: 'icon-512.png', sizes: '512x512', type: 'image/png', purpose: 'maskable' },
        ],
      },
      workbox: {
        // API calls always go to the network - this is live playback
        // control, never something to serve stale from cache.
        navigateFallbackDenylist: [/^\/api\//],
      },
    }),
  ],
  server: {
    proxy: {
      // Dev server proxies API calls to the real backend on the Pi, so
      // `pnpm dev` works against live data without deploying anything.
      '/api': 'http://10.0.0.198:5050',
    },
  },
})
