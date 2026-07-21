import { defineConfig } from 'vitest/config'

export default defineConfig({
  test: {
    environment: 'jsdom', // precisa de window/addEventListener p/ simular o pywebview
    globals: false,
  },
})
