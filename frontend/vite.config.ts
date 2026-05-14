import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  build: {
    rollupOptions: {
      output: {
        manualChunks: {
          'react-vendor':  ['react', 'react-dom', 'react-router-dom'],
          'query-vendor':  ['@tanstack/react-query'],
          'axios-vendor':  ['axios'],
        },
      },
    },
  },
})
