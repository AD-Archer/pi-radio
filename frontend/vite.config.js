import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      // Dev server proxies API calls to the real backend on the Pi, so
      // `pnpm dev` works against live data without deploying anything.
      '/api': 'http://10.0.0.198:5050',
    },
  },
})
