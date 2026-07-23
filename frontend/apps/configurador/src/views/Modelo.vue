<script setup lang="ts">
import { computed } from 'vue'
import { Card, StatusPill } from '@anta/ui'
import { store } from '../store'

const hw = () => store.hardware

// Tolerante a backend antigo (mock/versão sem os_label): cai nos campos crus.
const ambiente = computed(() => {
  const e = store.environment
  return {
    label: e?.os_label || e?.os || '—',
    detail: e?.detail || [e?.session, e?.desktop].filter(Boolean).join(' · '),
  }
})
</script>

<template>
  <div class="space-y-6">
    <!-- Resumo do hardware -->
    <div class="grid grid-cols-2 gap-3 sm:grid-cols-4">
      <div class="rounded-xl border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-900">
        <p class="text-xs uppercase tracking-wide text-slate-400">VRAM</p>
        <p class="mt-1 text-xl font-semibold">{{ hw()?.best_vram_gb ?? 0 }} <span class="text-sm font-normal text-slate-400">GB</span></p>
      </div>
      <div class="rounded-xl border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-900">
        <p class="text-xs uppercase tracking-wide text-slate-400">RAM</p>
        <p class="mt-1 text-xl font-semibold">{{ hw()?.ram_gb ?? 0 }} <span class="text-sm font-normal text-slate-400">GB</span></p>
      </div>
      <div class="rounded-xl border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-900">
        <p class="text-xs uppercase tracking-wide text-slate-400">Disco livre</p>
        <p class="mt-1 text-xl font-semibold">{{ hw()?.disk_free_gb ?? 0 }} <span class="text-sm font-normal text-slate-400">GB</span></p>
      </div>
      <div class="rounded-xl border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-900">
        <p class="text-xs uppercase tracking-wide text-slate-400">Ambiente</p>
        <!-- os_label/detail vêm prontos do Python: os campos crus davam "windows windows" -->
        <p class="mt-1 text-sm font-medium">{{ ambiente.label }}</p>
        <p class="text-xs text-slate-400">{{ ambiente.detail }}</p>
      </div>
    </div>

    <Card title="Escolha o modelo" subtitle="A cor indica se o modo roda no seu hardware (VRAM).">
      <!-- Famílias -->
      <div class="mb-4 flex flex-wrap gap-2">
        <button
          v-for="fam in store.catalog?.families ?? []"
          :key="fam.key"
          type="button"
          class="rounded-lg border px-3 py-1.5 text-sm font-medium transition-colors"
          :class="fam.key === store.form.family
            ? 'border-brand-700 bg-brand-700 text-white'
            : 'border-slate-300 text-slate-700 hover:bg-slate-50 dark:border-slate-700 dark:text-slate-200 dark:hover:bg-slate-800'"
          @click="store.setFamily(fam.key)"
        >{{ fam.label }}</button>
      </div>

      <!-- Modos da família -->
      <div class="overflow-hidden rounded-lg border border-slate-200 dark:border-slate-800">
        <table class="w-full text-left text-sm">
          <thead class="bg-slate-50 text-xs uppercase tracking-wide text-slate-400 dark:bg-slate-800/50">
            <tr>
              <th class="px-4 py-2 font-medium"></th>
              <th class="px-4 py-2 font-medium">Modo</th>
              <th class="px-4 py-2 font-medium">VRAM mín</th>
              <th class="px-4 py-2 font-medium">Modelo</th>
              <th class="px-4 py-2 font-medium">Status</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-slate-100 dark:divide-slate-800">
            <tr
              v-for="m in store.family()?.modes ?? []"
              :key="m.key"
              class="cursor-pointer transition-colors hover:bg-slate-50 dark:hover:bg-slate-800/50"
              :class="m.key === store.form.mode ? 'bg-brand-50 dark:bg-brand-900/30' : ''"
              @click="store.form.mode = m.key"
            >
              <td class="px-4 py-2">
                <span
                  class="flex h-4 w-4 items-center justify-center rounded-full border"
                  :class="m.key === store.form.mode ? 'border-brand-700' : 'border-slate-300 dark:border-slate-600'"
                >
                  <span v-if="m.key === store.form.mode" class="h-2 w-2 rounded-full bg-brand-700" />
                </span>
              </td>
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
      </div>
    </Card>
  </div>
</template>
