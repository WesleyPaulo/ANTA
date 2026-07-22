<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { hasPywebview, type RuntimeState } from '@anta/bridge'
import { Button } from '@anta/ui'
import { store } from './store'

onMounted(() => store.init())

const META: Record<RuntimeState, { label: string; hint: string }> = {
  carregando: { label: 'Carregando modelo', hint: 'Um instante…' },
  pronto: { label: 'Pronto', hint: 'Aperte o atalho ou o botão para falar' },
  ouvindo: { label: 'Ouvindo', hint: 'Aperte de novo para parar' },
  processando: { label: 'Processando', hint: 'Pensando…' },
  respondendo: { label: 'Respondendo', hint: '' },
  descarregado: { label: 'Modelo descarregado', hint: 'Carregue para usar de novo' },
  erro: { label: 'Ops', hint: '' },
}

const meta = computed(() => META[store.state])
const isMicError = computed(() => store.state === 'erro' && store.code === 'mic')
const isOff = computed(() => store.state === 'descarregado')
const podeDescarregar = computed(
  () => !['descarregado', 'carregando'].includes(store.state) && !store.busy,
)
const emBrowser = !hasPywebview()

const orbClass = computed(() => {
  switch (store.state) {
    case 'ouvindo': return 'bg-red-500'
    case 'respondendo': return 'bg-brand-500 animate-pulse'
    case 'carregando': return 'bg-brand-400 animate-pulse'
    case 'processando': return 'bg-brand-500'
    case 'pronto': return 'bg-brand-700'
    case 'descarregado': return 'bg-slate-400 dark:bg-slate-600'
    case 'erro': return 'bg-red-500'
    default: return 'bg-brand-700'
  }
})
</script>

<template>
  <div class="flex min-h-screen flex-col bg-white text-slate-800 dark:bg-slate-950 dark:text-slate-100">
    <!-- Barra de topo (arrastar/estado) -->
    <header class="flex items-center justify-between px-4 py-2">
      <div class="flex items-center gap-2">
        <div class="flex h-6 w-6 items-center justify-center rounded-md bg-brand-700 text-xs font-bold text-white">A</div>
        <span class="text-xs font-medium text-slate-500 dark:text-slate-400">ANTA</span>
      </div>
      <span
        v-if="emBrowser"
        class="rounded-full bg-slate-100 px-2 py-0.5 text-[10px] font-medium text-slate-500 dark:bg-slate-800 dark:text-slate-400"
      >mock</span>
    </header>

    <!-- Palco central -->
    <main class="flex flex-1 flex-col items-center justify-center gap-5 px-6 text-center">
      <!-- Orb animado por estado -->
      <div class="relative flex h-28 w-28 items-center justify-center">
        <span
          v-if="store.state === 'ouvindo'"
          class="absolute inline-flex h-full w-full animate-ping rounded-full bg-red-400 opacity-60"
        />
        <span
          v-if="store.state === 'processando'"
          class="absolute h-full w-full animate-spin rounded-full border-4 border-brand-300 border-t-transparent"
        />
        <span class="relative inline-flex h-20 w-20 rounded-full shadow-lg" :class="orbClass" />
      </div>

      <div>
        <p class="text-lg font-semibold">{{ meta.label }}</p>
        <p v-if="meta.hint" class="mt-0.5 text-sm text-slate-500 dark:text-slate-400">{{ meta.hint }}</p>
      </div>

      <!-- Texto da resposta / erro -->
      <p
        v-if="store.text && (store.state === 'respondendo' || store.state === 'erro')"
        class="max-h-24 overflow-y-auto rounded-lg bg-slate-50 px-3 py-2 text-sm text-slate-700 dark:bg-slate-900 dark:text-slate-200"
      >
        {{ store.text }}
      </p>

      <!-- Fluxo "não ouviu" -> abrir o Configurador (único que escreve o config) -->
      <div v-if="isMicError" class="w-full">
        <p class="mb-2 text-sm text-red-600 dark:text-red-400">Não captei áudio. Verifique o microfone.</p>
        <Button variant="secondary" class="w-full" @click="store.openConfigurador()">
          Abrir Configurador
        </Button>
      </div>
    </main>

    <!-- Controles -->
    <footer class="space-y-2 px-6 pb-6">
      <Button
        v-if="isOff"
        class="w-full justify-center"
        :disabled="store.busy"
        @click="store.load()"
      >
        Carregar modelo
      </Button>
      <Button
        v-else
        class="w-full justify-center"
        :disabled="store.state === 'carregando'"
        @click="store.toggle()"
      >
        {{ store.state === 'ouvindo' ? 'Parar' : 'Falar' }}
      </Button>

      <button
        v-if="podeDescarregar"
        type="button"
        class="w-full rounded-lg px-3 py-1.5 text-xs font-medium text-slate-500 hover:bg-slate-100 hover:text-slate-700 dark:text-slate-400 dark:hover:bg-slate-800 dark:hover:text-slate-200"
        @click="store.unload()"
      >
        Descarregar modelo da memória
      </button>
    </footer>
  </div>
</template>
