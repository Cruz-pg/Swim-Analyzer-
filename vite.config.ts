import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  root: 'frontend',
  plugins: [react()],
  build: { outDir: '../dist', emptyOutDir: true },
  server: {
    port: 5173,
    strictPort: true,
    proxy: { '/api': 'http://127.0.0.1:8000' },
    fs: { deny: ['.env', '.env.*', '*.{crt,pem}', '**/.git/**', '**/.venv/**'] },
  },
  preview: { proxy: { '/api': 'http://127.0.0.1:8000' } },
})
