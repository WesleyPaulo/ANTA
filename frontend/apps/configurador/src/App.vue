<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { isPywebview } from '@anta/bridge'
import { Button, Stepper } from '@anta/ui'
import { STEPS } from './router'
import { store } from './store'

const route = useRoute()
const router = useRouter()

const currentIndex = computed(() =>
  Math.max(0, STEPS.findIndex((s) => s.path === route.path)),
)
const isLast = computed(() => currentIndex.value === STEPS.length - 1)
const emBrowser = ref(false) // so vira true se o pywebview realmente nao aparecer

onMounted(async () => {
  store.init()
  emBrowser.value = !(await isPywebview())
})

function go(i: number) {
  router.push(STEPS[i].path)
}
function next() {
  if (!isLast.value) go(currentIndex.value + 1)
}
function prev() {
  if (currentIndex.value > 0) go(currentIndex.value - 1)
}
</script>

<template>
  <div class="min-h-screen bg-slate-50 text-slate-800 dark:bg-slate-950 dark:text-slate-100">
    <!-- Cabeçalho -->
    <header class="border-b border-slate-200 bg-white px-6 py-3 dark:border-slate-800 dark:bg-slate-900">
      <div class="mx-auto flex max-w-4xl items-center justify-between">
        <div class="flex items-center gap-3">
          <div class="flex h-8 w-8 items-center justify-center rounded-lg bg-brand-700 text-sm font-bold text-white">A</div>
          <div>
            <h1 class="text-sm font-semibold">ANTA — Configurador</h1>
            <p class="text-xs text-slate-500 dark:text-slate-400">
              {{ store.editMode ? 'Editar configuração' : 'Primeira configuração' }}
            </p>
          </div>
        </div>
        <span
          v-if="emBrowser"
          class="rounded-full bg-slate-200 px-2 py-0.5 text-xs font-medium text-slate-600 dark:bg-slate-800 dark:text-slate-300"
          title="Sem pywebview: dados vêm de um mock."
        >modo browser (mock)</span>
      </div>
    </header>

    <!-- Passos -->
    <div class="border-b border-slate-200 bg-white px-6 py-3 dark:border-slate-800 dark:bg-slate-900">
      <div class="mx-auto max-w-4xl">
        <Stepper :steps="STEPS" :current="currentIndex" :clickable="store.editMode" @go="go" />
      </div>
    </div>

    <main class="mx-auto max-w-4xl px-6 py-6">
      <!-- Carregando -->
      <div v-if="store.loading" class="rounded-xl border border-slate-200 bg-white p-8 text-center text-sm text-slate-500 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-400">
        Detectando hardware e carregando o catálogo…
      </div>
      <!-- Erro -->
      <div v-else-if="store.error" class="rounded-xl border border-red-200 bg-red-50 p-6 text-sm text-red-700 dark:border-red-900 dark:bg-red-950/40 dark:text-red-300">
        <p class="font-medium">Algo deu errado</p>
        <p class="mt-1">{{ store.error }}</p>
        <Button class="mt-3" variant="secondary" @click="store.init()">Tentar de novo</Button>
      </div>

      <!-- Conteúdo do passo -->
      <template v-else>
        <router-view v-slot="{ Component }">
          <transition name="fade" mode="out-in">
            <component :is="Component" />
          </transition>
        </router-view>

        <!-- Navegação (o passo "Instalar" tem o botão de salvar próprio) -->
        <div v-if="!isLast" class="mt-6 flex items-center justify-between">
          <Button variant="ghost" :disabled="currentIndex === 0" @click="prev">← Voltar</Button>
          <Button @click="next">Avançar →</Button>
        </div>
      </template>
    </main>
  </div>
</template>

<style scoped>
/* transicao suave entre passos do wizard */
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.18s ease, transform 0.18s ease;
}
.fade-enter-from {
  opacity: 0;
  transform: translateY(4px);
}
.fade-leave-to {
  opacity: 0;
  transform: translateY(-4px);
}
@media (prefers-reduced-motion: reduce) {
  .fade-enter-active,
  .fade-leave-active {
    transition: none;
  }
}
</style>
