<script setup lang="ts">
import { onBeforeUnmount, ref } from 'vue'

// Captura um atalho: clica "Gravar", aperta a combinação, ela vira "ctrl+alt+space".
const props = defineProps<{ modelValue: string }>()
const emit = defineEmits<{ 'update:modelValue': [string] }>()

const recording = ref(false)

const MODS = new Set(['Control', 'Alt', 'Shift', 'Meta'])
const SPECIAL: Record<string, string> = {
  ' ': 'space', Escape: 'esc', ArrowUp: 'up', ArrowDown: 'down',
  ArrowLeft: 'left', ArrowRight: 'right', Enter: 'enter', Tab: 'tab',
}

function keyToken(e: KeyboardEvent): string {
  if (e.key in SPECIAL) return SPECIAL[e.key]
  return e.key.length === 1 ? e.key.toLowerCase() : e.key.toLowerCase()
}

function onKeydown(e: KeyboardEvent) {
  if (!recording.value) return
  e.preventDefault()
  if (MODS.has(e.key)) return // só modificador: espera a tecla principal
  const parts: string[] = []
  if (e.ctrlKey) parts.push('ctrl')
  if (e.altKey) parts.push('alt')
  if (e.shiftKey) parts.push('shift')
  if (e.metaKey) parts.push('super')
  parts.push(keyToken(e))
  emit('update:modelValue', parts.join('+'))
  stop()
}

function start() {
  recording.value = true
  window.addEventListener('keydown', onKeydown, true)
}
function stop() {
  recording.value = false
  window.removeEventListener('keydown', onKeydown, true)
}
onBeforeUnmount(stop)
</script>

<template>
  <div class="flex items-center gap-3">
    <code
      class="min-w-[10rem] rounded-lg border border-slate-300 bg-slate-50 px-3 py-2 text-sm text-slate-800 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-100"
    >
      {{ recording ? 'aperte a combinação…' : props.modelValue || '—' }}
    </code>
    <button
      type="button"
      class="rounded-lg border border-slate-300 px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 dark:border-slate-700 dark:text-slate-200 dark:hover:bg-slate-800"
      @click="recording ? stop() : start()"
    >
      {{ recording ? 'Cancelar' : 'Gravar atalho' }}
    </button>
  </div>
</template>
