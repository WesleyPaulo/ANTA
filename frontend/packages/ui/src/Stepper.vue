<script setup lang="ts">
// Navegação por passos. Em modo edição (clickable) todos os passos são clicáveis;
// no wizard só os já visitados. O passo atual é azul escuro.
const props = withDefaults(
  defineProps<{
    steps: { key: string; label: string }[]
    current: number
    clickable?: boolean
  }>(),
  { clickable: false },
)
const emit = defineEmits<{ go: [number] }>()

function selectable(i: number): boolean {
  return props.clickable || i <= props.current
}
</script>

<template>
  <nav class="flex items-center gap-2">
    <template v-for="(s, i) in props.steps" :key="s.key">
      <button
        type="button"
        :disabled="!selectable(i)"
        class="flex items-center gap-2 rounded-full px-3 py-1.5 text-sm font-medium transition-colors disabled:cursor-not-allowed"
        :class="i === props.current
          ? 'bg-brand-700 text-white'
          : selectable(i)
            ? 'text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800'
            : 'text-slate-400 dark:text-slate-600'"
        @click="selectable(i) && emit('go', i)"
      >
        <span
          class="flex h-5 w-5 items-center justify-center rounded-full text-xs"
          :class="i === props.current ? 'bg-white/20' : 'bg-slate-200 dark:bg-slate-700'"
        >{{ i + 1 }}</span>
        {{ s.label }}
      </button>
      <span v-if="i < props.steps.length - 1" class="h-px w-4 bg-slate-200 dark:bg-slate-700" />
    </template>
  </nav>
</template>
