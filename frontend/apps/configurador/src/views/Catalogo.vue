<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { configApi, type Catalog, type EnvInfo, type Hardware } from '@anta/bridge'
import { StatusPill } from '@anta/ui'

// Toda chamada à ponte é async e falível (guia §3/§7): estados de carga e erro.
const carregando = ref(true)
const erro = ref<string | null>(null)
const hardware = ref<Hardware | null>(null)
const catalogo = ref<Catalog | null>(null)
const ambiente = ref<EnvInfo | null>(null)
const pong = ref<string>('')

async function carregar() {
  carregando.value = true
  erro.value = null
  try {
    // Em paralelo: um round-trip de smoke + as três leituras reais.
    const [p, hw, cat, env] = await Promise.all([
      configApi.ping(),
      configApi.getHardware(),
      configApi.getCatalog(),
      configApi.getEnvironment(),
    ])
    pong.value = p
    hardware.value = hw
    catalogo.value = cat
    ambiente.value = env
  } catch (e) {
    // Erro com direção (guia §7): diz o que fazer, não só "erro".
    erro.value = `Não consegui falar com o backend (${String(e)}). ` +
      'Verifique se a janela foi aberta por "anta config".'
  } finally {
    carregando.value = false
  }
}

onMounted(carregar)
</script>

<template>
  <div>
    <!-- Carregando -->
    <div v-if="carregando" class="rounded-lg border border-slate-200 bg-white p-6 text-sm text-slate-500 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-400">
      Detectando hardware e carregando o catálogo…
    </div>

    <!-- Erro (com direção) -->
    <div v-else-if="erro" class="rounded-lg border border-red-200 bg-red-50 p-6 text-sm text-red-700 dark:border-red-800 dark:bg-red-900/30 dark:text-red-300">
      <p class="font-medium">Algo deu errado</p>
      <p class="mt-1">{{ erro }}</p>
      <button
        class="mt-3 rounded-md bg-red-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-red-700"
        @click="carregar"
      >
        Tentar de novo
      </button>
    </div>

    <!-- Conteúdo -->
    <div v-else class="space-y-6">
      <!-- Resumo do hardware -->
      <section class="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <div class="rounded-lg border border-slate-200 bg-white p-4 dark:border-slate-700 dark:bg-slate-800">
          <p class="text-xs uppercase tracking-wide text-slate-400">VRAM</p>
          <p class="mt-1 text-xl font-semibold">{{ hardware?.best_vram_gb ?? 0 }} <span class="text-sm font-normal text-slate-400">GB</span></p>
        </div>
        <div class="rounded-lg border border-slate-200 bg-white p-4 dark:border-slate-700 dark:bg-slate-800">
          <p class="text-xs uppercase tracking-wide text-slate-400">RAM</p>
          <p class="mt-1 text-xl font-semibold">{{ hardware?.ram_gb ?? 0 }} <span class="text-sm font-normal text-slate-400">GB</span></p>
        </div>
        <div class="rounded-lg border border-slate-200 bg-white p-4 dark:border-slate-700 dark:bg-slate-800">
          <p class="text-xs uppercase tracking-wide text-slate-400">Disco livre</p>
          <p class="mt-1 text-xl font-semibold">{{ hardware?.disk_free_gb ?? 0 }} <span class="text-sm font-normal text-slate-400">GB</span></p>
        </div>
        <div class="rounded-lg border border-slate-200 bg-white p-4 dark:border-slate-700 dark:bg-slate-800">
          <p class="text-xs uppercase tracking-wide text-slate-400">Ambiente</p>
          <p class="mt-1 text-sm font-medium">{{ ambiente?.os }} · {{ ambiente?.session }}</p>
          <p class="text-xs text-slate-400">atalho: {{ ambiente?.hotkey_strategy }}</p>
        </div>
      </section>

      <p v-if="hardware?.gpus?.length" class="text-xs text-slate-400">
        GPU: {{ hardware.gpus.map((g) => g.name).join(', ') }} · ponte: {{ pong }}
      </p>

      <!-- Catálogo: famílias × modos, com o gate de VRAM -->
      <section
        v-for="fam in catalogo?.families ?? []"
        :key="fam.key"
        class="rounded-lg border border-slate-200 bg-white dark:border-slate-700 dark:bg-slate-800"
      >
        <header class="border-b border-slate-100 px-4 py-3 dark:border-slate-700">
          <h2 class="text-sm font-semibold">{{ fam.label }}</h2>
        </header>
        <table class="w-full text-left text-sm">
          <thead class="text-xs uppercase tracking-wide text-slate-400">
            <tr>
              <th class="px-4 py-2 font-medium">Modo</th>
              <th class="px-4 py-2 font-medium">VRAM mín</th>
              <th class="px-4 py-2 font-medium">Modelo (LLM)</th>
              <th class="px-4 py-2 font-medium">Status</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-slate-100 dark:divide-slate-700">
            <tr v-for="m in fam.modes" :key="m.key">
              <td class="px-4 py-2">
                <div class="font-medium">{{ m.label }}</div>
                <div class="text-xs text-slate-400">{{ m.description }}</div>
              </td>
              <td class="px-4 py-2 tabular-nums">{{ m.vram_gb }} GB</td>
              <td class="px-4 py-2"><code class="text-xs">{{ m.llm }}</code></td>
              <td class="px-4 py-2"><StatusPill :status="m.status" /></td>
            </tr>
          </tbody>
        </table>
      </section>
    </div>
  </div>
</template>
