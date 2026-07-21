<script setup lang="ts">
// Pílula de status do gate de VRAM. As classes ficam como strings COMPLETAS
// (não interpoladas) para o purge do Tailwind enxergá-las — por isso o lookup.
type Status = 'verde' | 'amarelo' | 'vermelho'

const props = withDefaults(
  defineProps<{ status: Status; label?: string }>(),
  { label: undefined },
)

const STYLES: Record<Status, string> = {
  verde: 'bg-green-100 text-green-800 ring-green-600/20 dark:bg-green-900/40 dark:text-green-300',
  amarelo: 'bg-yellow-100 text-yellow-800 ring-yellow-600/20 dark:bg-yellow-900/40 dark:text-yellow-300',
  vermelho: 'bg-red-100 text-red-800 ring-red-600/20 dark:bg-red-900/40 dark:text-red-300',
}

const DEFAULT_TEXT: Record<Status, string> = {
  verde: 'Roda',
  amarelo: 'Aperta',
  vermelho: 'Nao roda',
}
</script>

<template>
  <span
    class="inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ring-1 ring-inset"
    :class="STYLES[props.status]"
  >
    {{ props.label ?? DEFAULT_TEXT[props.status] }}
  </span>
</template>
