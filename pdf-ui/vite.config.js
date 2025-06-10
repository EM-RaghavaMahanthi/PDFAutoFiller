import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    proxy: {
      // Flask endpoints
      '/start': 'http://localhost:5050',
      '/stream': 'http://localhost:5050',
      '/download': 'http://localhost:5050'
    }
  }
})
