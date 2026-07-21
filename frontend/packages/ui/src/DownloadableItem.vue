<script setup lang="ts">
// Componente genérico "item baixável" (guia §4.2): reusado p/ LLM/STT/TTS/embedding.
// catálogo -> escolha -> download -> verificação. O pai controla o estado.
type State = 'idle' | 'downloading' | 'done' | 'error'

const props = withDefaults(
  defineProps<{
    title: string
    tag?: string // ex.: o modelo (qwen3:4b) ou a voz
    subtitle?: string
    state?: State
    pct?: number | null
    installed?: boolean | null
    error?: string
  }>(),
  { state: 'idle', pct: null, installed: null },
)
const emit = defineEmits<{ download: [] }>()
</script>

<template>
  <div class="flex items-center gap-4 rounded-lg border border-slate-200 px-4 py-3 dark:border-slate-800">
    <div class="min-w-0 flex-1">
      <div class="flex items-center gap-2">
        <span class="truncate text-sm font-medium text-slate-800 dark:text-slate-100">{{ props.title }}</span>
        <code v-if="props.tag" class="truncate text-xs text-slate-500 dark:text-slate-400">{{ props.tag }}</code>
      </div>
      <p v-if="props.subtitle" class="text-xs text-slate-500 dark:text-slate-400">{{ props.subtitle }}</p>

      <!-- barra de progresso -->
      <div
        v-if="props.state === 'downloading'"
        class="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-slate-200 dark:bg-slate-700"
      >
        <div
          class="h-full rounded-full bg-brand-600 transition-all"
          :style="{ width: (props.pct ?? 0) + '%' }"
        />
      </div>
      <p v-if="props.state === 'error'" class="mt-1 text-xs text-red-600 dark:text-red-400">{{ props.error }}</p>
    </div>

    <!-- estado / ação -->
    <div class="shrink-0">
      <span v-if="props.state === 'done' || props.installed === true" class="text-sm font-medium text-green-600 dark:text-green-400">
        ✓ pronto
      </span>
      <span v-else-if="props.state === 'downloading'" class="text-sm tabular-nums text-slate-500 dark:text-slate-400">
        {{ props.pct != null ? props.pct + '%' : '…' }}
      </span>
      <button
        v-else
        type="button"
        class="rounded-lg bg-brand-700 px-3 py-1.5 text-xs font-medium text-white hover:bg-brand-600"
        @click="emit('download')"
      >
        {{ props.state === 'error' ? 'Tentar de novo' : 'Baixar' }}
      </button>
    </div>
  </div>
</template>
