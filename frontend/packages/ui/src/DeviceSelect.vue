<script setup lang="ts">
// Select rotulado para listas de devices (mic/saida) ou strings.
// Aceita options como string[] ou {name}[]. Valor '' = "(padrão do sistema)".
const props = withDefaults(
  defineProps<{
    modelValue: string | null
    options: Array<string | { name: string }>
    label?: string
    placeholder?: string
  }>(),
  { placeholder: '(padrão do sistema)' },
)
const emit = defineEmits<{ 'update:modelValue': [string | null] }>()

function nome(o: string | { name: string }): string {
  return typeof o === 'string' ? o : o.name
}
function onChange(e: Event) {
  const v = (e.target as HTMLSelectElement).value
  emit('update:modelValue', v === '' ? null : v)
}
</script>

<template>
  <label class="block">
    <span v-if="props.label" class="mb-1 block text-xs font-medium uppercase tracking-wide text-slate-400">
      {{ props.label }}
    </span>
    <select
      class="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-800 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
      :value="props.modelValue ?? ''"
      @change="onChange"
    >
      <option value="">{{ props.placeholder }}</option>
      <option v-for="o in props.options" :key="nome(o)" :value="nome(o)">{{ nome(o) }}</option>
    </select>
  </label>
</template>
