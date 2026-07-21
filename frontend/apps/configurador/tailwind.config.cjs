const preset = require('@anta/ui/tailwind-preset')

/** @type {import('tailwindcss').Config} */
module.exports = {
  presets: [preset],
  darkMode: 'media',
  content: [
    './index.html',
    './src/**/*.{vue,ts}',
    // Componentes compartilhados: o purge precisa ver as classes do @anta/ui.
    '../../packages/ui/src/**/*.{vue,ts}',
  ],
}
