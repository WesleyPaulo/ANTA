import { fileURLToPath, URL } from 'node:url'
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// base:'./' -> assets relativos (obrigatorio sob file:// no build; guia §7).
export default defineConfig({
  base: './',
  plugins: [vue()],
  resolve: {
    alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) },
  },
  // Pacotes internos do workspace sao codigo-fonte (.ts/.vue), nao pre-bundlar.
  optimizeDeps: {
    exclude: ['@anta/bridge', '@anta/ui'],
  },
  server: {
    port: 5173,
    strictPort: true,
  },
})
