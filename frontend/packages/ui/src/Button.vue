<script setup lang="ts">
// Botão da paleta: primary = azul escuro; secondary/ghost = neutro;
// danger = vermelho (parar/interromper — a única ação destrutiva do HUD).
type Variant = 'primary' | 'secondary' | 'ghost' | 'danger'

const props = withDefaults(
  defineProps<{ variant?: Variant; disabled?: boolean; type?: 'button' | 'submit' }>(),
  { variant: 'primary', disabled: false, type: 'button' },
)

const VARIANTS: Record<Variant, string> = {
  primary:
    'bg-brand-700 text-white hover:bg-brand-600 focus-visible:ring-brand-500 ' +
    'disabled:bg-slate-300 dark:disabled:bg-slate-700',
  secondary:
    'border border-slate-300 bg-white text-slate-800 hover:bg-slate-50 focus-visible:ring-brand-500 ' +
    'dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100 dark:hover:bg-slate-800',
  ghost:
    'text-slate-600 hover:bg-slate-100 focus-visible:ring-brand-500 ' +
    'dark:text-slate-300 dark:hover:bg-slate-800',
  danger:
    'bg-red-600 text-white hover:bg-red-500 focus-visible:ring-red-500 ' +
    'disabled:bg-slate-300 dark:disabled:bg-slate-700',
}
</script>

<template>
  <button
    :type="props.type"
    :disabled="props.disabled"
    class="inline-flex items-center justify-center gap-2 rounded-lg px-4 py-2 text-sm font-medium transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-offset-1 disabled:cursor-not-allowed disabled:opacity-70 dark:focus-visible:ring-offset-slate-900"
    :class="VARIANTS[props.variant]"
  >
    <slot />
  </button>
</template>
