<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { isPywebview, type RuntimeState } from '@anta/bridge'
import { Button } from '@anta/ui'
import { store } from './store'

const emBrowser = ref(false) // so vira true se o pywebview realmente nao aparecer
onMounted(async () => {
  store.init()
  emBrowser.value = !(await isPywebview())
})

const META: Record<RuntimeState, { label: string; hint: string }> = {
  carregando: { label: 'Carregando modelo', hint: 'Um instante…' },
  pronto: { label: 'Pronto', hint: 'Aperte o atalho ou o botão para falar' },
  ouvindo: { label: 'Ouvindo', hint: 'Aperte de novo para parar e enviar' },
  processando: { label: 'Processando', hint: 'Pensando… toque em Parar para cancelar' },
  respondendo: { label: 'Respondendo', hint: 'Falando… toque em Parar para interromper' },
  descarregado: { label: 'Memória desalocada', hint: 'A ANTA está pausada até você carregar' },
  erro: { label: 'Ops', hint: '' },
}

const meta = computed(() => META[store.state])
const isMicError = computed(() => store.state === 'erro' && store.code === 'mic')
const isOff = computed(() => store.state === 'descarregado')

// O botão principal muda de PAPEL com o estado — não só de rótulo. Enquanto a ANTA
// respondia (TTS falando) ele ficava "Falar" e ativo: clicar não parava nada e ainda
// enfileirava uma gravação para quando o turno acabasse.
type Acao = 'toggle' | 'cancel' | 'load' | 'nada'
const botao = computed<{ label: string; acao: Acao; variant: 'primary' | 'danger'; disabled: boolean }>(() => {
  switch (store.state) {
    case 'descarregado':
      return { label: 'Carregar memória', acao: 'load', variant: 'primary', disabled: store.busy }
    case 'carregando':
      return { label: 'Carregando…', acao: 'nada', variant: 'primary', disabled: true }
    case 'ouvindo':
      return { label: 'Parar e enviar', acao: 'toggle', variant: 'danger', disabled: false }
    case 'processando':
      return { label: 'Parar', acao: 'cancel', variant: 'danger', disabled: false }
    case 'respondendo':
      return { label: 'Parar', acao: 'cancel', variant: 'danger', disabled: false }
    default:
      return { label: 'Falar', acao: 'toggle', variant: 'primary', disabled: store.busy }
  }
})

function acionar() {
  const { acao } = botao.value
  if (acao === 'toggle') store.toggle()
  else if (acao === 'cancel') store.cancel()
  else if (acao === 'load') store.load()
}

const podeDesalocar = computed(
  () => !['descarregado', 'carregando'].includes(store.state) && !store.busy,
)

// Linha de memória: a prova de que o app residente está vivo e o que ele custa.
const memoria = computed(() => {
  const m = store.memoria
  if (!m) return ''
  const partes: string[] = []
  if (m.vram_used_gb !== null && m.vram_total_gb !== null) {
    partes.push(`VRAM ${m.vram_used_gb.toFixed(1)}/${m.vram_total_gb.toFixed(1)} GB`)
  }
  if (m.ram_used_gb !== null) partes.push(`RAM ${m.ram_used_gb.toFixed(1)} GB`)
  return partes.join(' · ')
})

// cor + halo (ring) por estado — classes completas p/ o purge do Tailwind ver
const orbClass = computed(() => {
  switch (store.state) {
    case 'ouvindo': return 'bg-red-500 ring-4 ring-red-400/50'
    case 'respondendo': return 'bg-brand-500 ring-4 ring-brand-400/40 animate-pulse'
    case 'carregando': return 'bg-brand-400 ring-4 ring-brand-300/40 animate-pulse'
    case 'processando': return 'bg-brand-500 ring-4 ring-brand-300/40'
    case 'pronto': return 'bg-brand-700 ring-4 ring-brand-500/30'
    case 'descarregado': return 'bg-slate-400 ring-4 ring-slate-300/30 dark:bg-slate-600'
    case 'erro': return 'bg-red-500 ring-4 ring-red-400/40'
    default: return 'bg-brand-700 ring-4 ring-brand-500/30'
  }
})
// "respira" so quando ocioso (pronto), pra nao parecer travado
const orbBreathe = computed(() => (store.state === 'pronto' ? 'orb-breathe' : ''))
</script>

<template>
  <div class="flex min-h-screen flex-col bg-gradient-to-b from-white to-slate-50 text-slate-800 dark:from-slate-950 dark:to-slate-900 dark:text-slate-100">
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
        <span
          class="relative inline-flex h-20 w-20 rounded-full shadow-lg transition-all duration-500 ease-out"
          :class="[orbClass, orbBreathe]"
        />
      </div>

      <div>
        <p class="text-lg font-semibold">{{ meta.label }}</p>
        <p v-if="meta.hint" class="mt-0.5 text-sm text-slate-500 dark:text-slate-400">{{ meta.hint }}</p>
      </div>

      <!-- Resposta: persiste até a próxima fala (antes só ia pro log/voz) -->
      <p
        v-if="store.resposta && store.state !== 'erro'"
        class="max-h-32 w-full overflow-y-auto rounded-lg bg-slate-50 px-3 py-2 text-sm text-slate-700 dark:bg-slate-900 dark:text-slate-200"
      >
        {{ store.resposta }}
      </p>

      <!-- Erro (com detalhe do backend) -->
      <p
        v-else-if="store.state === 'erro' && store.erro && !isMicError"
        class="max-h-32 w-full overflow-y-auto rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700 dark:bg-red-950/40 dark:text-red-300"
      >
        {{ store.erro }}
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
    <footer class="space-y-2 px-6 pb-5">
      <Button
        class="w-full justify-center"
        :variant="botao.variant"
        :disabled="botao.disabled"
        @click="acionar()"
      >
        {{ botao.label }}
      </Button>

      <button
        v-if="podeDesalocar"
        type="button"
        class="w-full rounded-lg px-3 py-1.5 text-xs font-medium text-slate-500 hover:bg-slate-100 hover:text-slate-700 dark:text-slate-400 dark:hover:bg-slate-800 dark:hover:text-slate-200"
        @click="store.unload()"
      >
        Desalocar memória
      </button>

      <!-- O que a ANTA ocupa agora: um residente sem número na tela vira suspeita -->
      <p class="h-4 text-center text-[11px] text-slate-400 dark:text-slate-500">
        <template v-if="isOff">Memória liberada — a ANTA está pausada</template>
        <template v-else>{{ memoria }}</template>
      </p>
    </footer>
  </div>
</template>

<style scoped>
/* "respira" quando ocioso (pronto): escala suave, sem parecer travado */
@keyframes orb-breathe {
  0%, 100% { transform: scale(1); }
  50% { transform: scale(1.06); }
}
.orb-breathe {
  animation: orb-breathe 3.2s ease-in-out infinite;
}
@media (prefers-reduced-motion: reduce) {
  .orb-breathe { animation: none; }
}
</style>
