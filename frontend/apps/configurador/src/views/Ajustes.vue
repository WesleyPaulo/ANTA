<script setup lang="ts">
import { ref, watch } from 'vue'
import { configApi } from '@anta/bridge'
import { Card, HotkeyCapture, Toggle } from '@anta/ui'
import { store } from '../store'

const hotkeyMsg = ref<string | null>(null)

watch(
  () => store.form.hotkey,
  async (hk) => {
    const r = await configApi.validateHotkey(hk)
    hotkeyMsg.value = r.valid ? null : r.msg
    if (r.valid) store.form.hotkey = r.normalized
  },
)

const envHint = () => {
  const e = store.environment
  if (!e) return ''
  if (e.hotkey_strategy === 'compositor') return 'Wayland/KDE: o atalho é registrado no sistema (via "anta toggle").'
  if (e.captures_hotkey_in_process) return 'A ANTA captura o atalho direto (X11/Windows).'
  return 'Você vinculará o atalho manualmente ao "anta toggle".'
}
</script>

<template>
  <div class="space-y-6">
    <Card title="Atalho global" subtitle="A tecla que ativa/encerra a fala (push-to-talk).">
      <HotkeyCapture v-model="store.form.hotkey" />
      <p v-if="hotkeyMsg" class="mt-2 text-xs text-red-600 dark:text-red-400">{{ hotkeyMsg }}</p>
      <p class="mt-2 text-xs text-slate-500 dark:text-slate-400">{{ envHint() }}</p>
    </Card>

    <Card title="Notas" subtitle="Onde a ANTA salva notas/documentos (e busca com RAG).">
      <label class="block">
        <span class="mb-1 block text-xs font-medium uppercase tracking-wide text-slate-400">Pasta do vault</span>
        <input
          v-model="store.form.obsidian_vault"
          type="text"
          placeholder="vazio = ~/anta-notas"
          class="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-800 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
        />
      </label>
      <div class="mt-4 border-t border-slate-100 pt-4 dark:border-slate-800">
        <Toggle v-model="store.form.rag" label="Memória e busca nas notas (RAG)" hint="Embedding na CPU; não toca a VRAM." />
      </div>
    </Card>

    <Card title="Busca na web" subtitle="Opt-in: rompe o offline. Desligado por padrão.">
      <Toggle v-model="store.form.web" label="Permitir busca na web" hint="A consulta sai para um buscador." />
      <div v-if="store.form.web" class="mt-4 space-y-3 border-t border-slate-100 pt-4 dark:border-slate-800">
        <label class="block">
          <span class="mb-1 block text-xs font-medium uppercase tracking-wide text-slate-400">Buscador</span>
          <select
            v-model="store.form.web_engine"
            class="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-800 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
          >
            <option value="duckduckgo">DuckDuckGo (sem chave)</option>
            <option value="searxng">SearXNG</option>
          </select>
        </label>
        <label v-if="store.form.web_engine === 'searxng'" class="block">
          <span class="mb-1 block text-xs font-medium uppercase tracking-wide text-slate-400">URL do SearXNG</span>
          <input
            v-model="store.form.web_searxng_url"
            type="text"
            placeholder="http://localhost:8080"
            class="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-800 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
          />
        </label>
      </div>
    </Card>
  </div>
</template>
