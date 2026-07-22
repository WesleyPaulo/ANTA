import { fileURLToPath, URL } from 'node:url'
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// base:'./' -> assets relativos (file:// no build). Porta 5174 (o Configurador usa 5173).
export default defineConfig({
  base: './',
  plugins: [vue()],
  resolve: {
    alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) },
  },
  optimizeDeps: {
    exclude: ['@anta/bridge', '@anta/ui'],
  },
  server: {
    port: 5174,
    strictPort: true,
  },
})
