import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Dev: `npm run dev` serves the SPA on :5173 and proxies API calls to the FastAPI dev server on
// :8000, so the browser talks to one origin (no CORS needed in dev, mirroring prod where FastAPI
// serves the built app itself). Prod: `npm run build` -> dist/, which FastAPI serves.
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/chat': 'http://localhost:8000',
      '/summary': 'http://localhost:8000',
      '/profile': 'http://localhost:8000',
      '/onboarding': 'http://localhost:8000',
      '/config': 'http://localhost:8000',
      '/health': 'http://localhost:8000',
      '/protected-ping': 'http://localhost:8000',
    },
  },
  build: {
    outDir: 'dist',
  },
})
