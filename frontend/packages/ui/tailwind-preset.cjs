// Preset Tailwind compartilhado pelas duas apps. Cada app faz `presets: [este]`
// no seu tailwind.config e adiciona so o seu `content`.
/** @type {import('tailwindcss').Config} */
module.exports = {
  theme: {
    extend: {
      colors: {
        // Semantica do gate de VRAM (status_for -> verde/amarelo/vermelho).
        status: {
          verde: '#16a34a',
          amarelo: '#ca8a04',
          vermelho: '#dc2626',
        },
      },
    },
  },
  plugins: [],
}
