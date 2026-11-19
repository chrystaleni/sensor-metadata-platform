import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import {configDefaults} from 'vitest/config'

export default defineConfig({
  plugins: [react()],
  server: { proxy: { '/ready': { target: process.env.VITE_PROXY_TARGET || 'http://localhost:8000', changeOrigin: true }, '/api': { target: process.env.VITE_PROXY_TARGET || 'http://localhost:8000', changeOrigin: true } } },
  test: {
    exclude: [...configDefaults.exclude, 'e2e/**'],
    environment: 'jsdom',
    setupFiles: './src/test-setup.js',
    globals: true,
    css: true,
  },
})
