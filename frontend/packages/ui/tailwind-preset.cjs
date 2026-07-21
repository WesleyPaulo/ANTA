// Preset Tailwind compartilhado pelas duas apps (paleta da ANTA).
// Identidade: PRETO/BRANCO + AZUL ESCURO. Neutros = slate (cinza levemente frio,
// casa com o azul); acento unico de marca = `brand` (azul escuro/navy). As cores de
// STATUS (verde/ambar/vermelho) ficam so nas pilulas do gate de VRAM — sao
// funcionais (roda/aperta/nao roda), nao decorativas.
/** @type {import('tailwindcss').Config} */
module.exports = {
  theme: {
    extend: {
      colors: {
        // Azul escuro — o unico acento de marca.
        brand: {
          50: '#eef3fb',
          100: '#d6e2f4',
          200: '#aec6e8',
          300: '#7fa3d6',
          400: '#4f7cbf',
          500: '#2f5da3',
          600: '#234b86', // hover
          700: '#1c3d6e', // botoes primarios (azul escuro)
          800: '#182f52',
          900: '#122238', // superficies navy profundas
          950: '#0b1524', // quase-preto azulado (fundo dark)
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'Segoe UI', 'Roboto', 'sans-serif'],
      },
    },
  },
  plugins: [],
}
