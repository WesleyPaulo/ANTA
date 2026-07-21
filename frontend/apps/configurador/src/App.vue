<script setup lang="ts">
import { hasPywebview } from '@anta/bridge'

// Só para o cabeçalho sinalizar em que modo a UI está rodando.
const emBrowser = !hasPywebview()
</script>

<template>
  <div class="min-h-screen bg-slate-50 text-slate-800 dark:bg-slate-900 dark:text-slate-100">
    <header class="border-b border-slate-200 bg-white px-6 py-4 dark:border-slate-700 dark:bg-slate-800">
      <div class="flex items-center justify-between">
        <div>
          <h1 class="text-lg font-semibold">ANTA — Configurador</h1>
          <p class="text-xs text-slate-500 dark:text-slate-400">
            Fundação (walking skeleton) · escolha o modelo pelo seu hardware
          </p>
        </div>
        <span
          v-if="emBrowser"
          class="rounded-full bg-slate-200 px-2 py-0.5 text-xs font-medium text-slate-600 dark:bg-slate-700 dark:text-slate-300"
          title="Sem pywebview: os dados vêm de um mock."
        >
          modo browser (mock)
        </span>
      </div>
    </header>

    <main class="mx-auto max-w-4xl px-6 py-6">
      <router-view />
    </main>
  </div>
</template>
