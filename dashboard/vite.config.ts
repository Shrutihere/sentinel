import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// In dev, proxy API calls to the backend so the dashboard can use same-origin
// relative paths (no CORS needed). In the container the API serves the built
// dashboard directly, so relative paths just work there too.
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/v1': 'http://127.0.0.1:8000',
      '/health': 'http://127.0.0.1:8000',
    },
  },
})
