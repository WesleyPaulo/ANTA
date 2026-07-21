<script setup lang="ts">
// Switch booleano (v-model). Ligado = azul escuro.
const props = defineProps<{ modelValue: boolean; label?: string; hint?: string }>()
const emit = defineEmits<{ 'update:modelValue': [boolean] }>()
</script>

<template>
  <label class="flex cursor-pointer items-start justify-between gap-4">
    <span v-if="props.label || props.hint">
      <span class="block text-sm font-medium text-slate-800 dark:text-slate-100">{{ props.label }}</span>
      <span v-if="props.hint" class="block text-xs text-slate-500 dark:text-slate-400">{{ props.hint }}</span>
    </span>
    <button
      type="button"
      role="switch"
      :aria-checked="props.modelValue"
      class="relative inline-flex h-6 w-11 shrink-0 items-center rounded-full transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500"
      :class="props.modelValue ? 'bg-brand-700' : 'bg-slate-300 dark:bg-slate-700'"
      @click="emit('update:modelValue', !props.modelValue)"
    >
      <span
        class="inline-block h-5 w-5 transform rounded-full bg-white shadow transition-transform"
        :class="props.modelValue ? 'translate-x-5' : 'translate-x-0.5'"
      />
    </button>
  </label>
</template>
