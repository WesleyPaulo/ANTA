<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { configApi, type ComponentKind, type OllamaStatus } from '@anta/bridge'
import { Button, Card, DownloadableItem } from '@anta/ui'
import { store } from '../store'

const salvando = ref(false)
const baixandoTudo = ref(false)
const resultado = ref<{ ok: boolean; msg: string } | null>(null)

// Ollama: o motor do LLM (unica dep externa que nao vai no bundle)
const ollama = ref<OllamaStatus | null>(null)
const ollamaChecando = ref(true)
const ollamaInstalando = ref(false)
const ollamaManual = ref<string | null>(null)

async function checarOllama() {
  ollamaChecando.value = true
  try {
    ollama.value = await configApi.ollamaStatus()
  } finally {
    ollamaChecando.value = false
  }
}

async function instalarOllama() {
  ollamaInstalando.value = true
  ollamaManual.value = null
  try {
    const r = await configApi.installOllama()
    if (r.manual) ollamaManual.value = r.manual
    await checarOllama()
  } finally {
    ollamaInstalando.value = false
  }
}

onMounted(checarOllama)

// A voz pode vir como caminho completo (config antiga) — mostra so o nome do arquivo.
const vozLabel = computed(() => {
  if (!store.form.tts) return 'desligado'
  const v = store.form.tts_voice
  if (!v) return 'padrão'
  return (v.split(/[\\/]/).pop() ?? v).replace(/\.onnx$/i, '')
})

type Comp = { kind: ComponentKind; title: string; tag: string; subtitle: string }

const componentes = computed<Comp[]>(() => {
  const m = store.mode()
  if (!m) return []
  const list: Comp[] = [
    { kind: 'llm', title: 'Modelo de linguagem (LLM)', tag: m.llm, subtitle: 'Baixado pelo Ollama.' },
    { kind: 'stt', title: 'Reconhecimento de fala (STT)', tag: m.stt, subtitle: 'Whisper na CPU.' },
  ]
  if (store.form.rag) {
    list.push({ kind: 'rag_embedder', title: 'Memória/busca (embedding)', tag: 'MiniLM multilingue', subtitle: 'Na CPU.' })
  }
  if (store.form.tts) {
    list.push({ kind: 'tts_voice', title: 'Voz (TTS)', tag: store.form.tts_voice ?? store.voices?.default ?? 'pt_BR', subtitle: 'Piper.' })
  }
  return list
})

function keyFor(c: Comp): string {
  if (c.kind === 'rag_embedder') return ''
  if (c.kind === 'tts_voice') return store.form.tts_voice ?? store.voices?.default ?? 'pt_BR-faber-medium'
  return c.tag
}

function estado(kind: string) {
  const p = store.progress[kind]
  if (!p) return { state: 'idle' as const, pct: null as number | null, error: '' }
  if (p.phase === 'done') return { state: 'done' as const, pct: 100, error: '' }
  if (p.phase === 'error') return { state: 'error' as const, pct: null, error: p.text }
  return { state: 'downloading' as const, pct: p.pct, error: '' }
}

async function baixar(c: Comp) {
  await configApi.downloadComponent(c.kind, keyFor(c))
}

async function baixarTudo() {
  baixandoTudo.value = true
  try {
    for (const c of componentes.value) await baixar(c)
  } finally {
    baixandoTudo.value = false
  }
}

async function salvar() {
  salvando.value = true
  resultado.value = null
  try {
    const r = await configApi.save(store.toConfig())
    resultado.value = r.ok
      ? { ok: true, msg: `A ANTA foi configurada.${r.warnings?.length ? ' Avisos: ' + r.warnings.join('; ') : ''}` }
      : { ok: false, msg: r.msg ?? 'Falha ao salvar.' }
    if (r.ok) store.editMode = true
  } finally {
    salvando.value = false
  }
}
</script>

<template>
  <div class="space-y-6">
    <!-- Revisão -->
    <Card title="Revisão" subtitle="Confira antes de instalar.">
      <dl class="grid grid-cols-2 gap-x-6 gap-y-3 text-sm sm:grid-cols-3">
        <div class="min-w-0"><dt class="text-xs uppercase tracking-wide text-slate-400">Família</dt><dd class="truncate font-medium">{{ store.family()?.label }}</dd></div>
        <div class="min-w-0"><dt class="text-xs uppercase tracking-wide text-slate-400">Modo</dt><dd class="truncate font-medium">{{ store.mode()?.label }}</dd></div>
        <div class="min-w-0"><dt class="text-xs uppercase tracking-wide text-slate-400">Microfone</dt><dd class="truncate font-medium" :title="store.form.mic_device ?? ''">{{ store.form.mic_device ?? 'padrão' }}</dd></div>
        <div class="min-w-0"><dt class="text-xs uppercase tracking-wide text-slate-400">Voz (TTS)</dt><dd class="truncate font-medium" :title="store.form.tts_voice ?? ''">{{ vozLabel }}</dd></div>
        <div class="min-w-0"><dt class="text-xs uppercase tracking-wide text-slate-400">Atalho</dt><dd class="truncate font-medium"><code class="text-xs">{{ store.form.hotkey }}</code></dd></div>
        <div class="min-w-0"><dt class="text-xs uppercase tracking-wide text-slate-400">RAG / Web</dt><dd class="truncate font-medium">{{ store.form.rag ? 'RAG on' : 'RAG off' }} · {{ store.form.web ? 'web on' : 'web off' }}</dd></div>
      </dl>
    </Card>

    <!-- Ollama (motor do LLM) -->
    <div v-if="ollamaChecando" class="rounded-xl border border-slate-200 bg-white px-5 py-3 text-sm text-slate-500 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-400">
      Verificando o Ollama…
    </div>
    <div
      v-else-if="ollama && (!ollama.installed || !ollama.running)"
      class="rounded-xl border border-amber-300 bg-amber-50 p-4 dark:border-amber-800 dark:bg-amber-950/30"
    >
      <p class="text-sm font-medium text-amber-800 dark:text-amber-300">
        {{ ollama.installed ? 'Ollama instalado, mas não está no ar' : 'Ollama não encontrado' }}
      </p>
      <p class="mt-1 text-xs text-amber-700 dark:text-amber-400">
        O Ollama é o motor que roda o modelo de linguagem (a única peça que não vem no pacote).
        {{ ollama.installed ? 'Inicie o Ollama e verifique de novo.' : '' }}
      </p>
      <div class="mt-3 flex flex-wrap items-center gap-2">
        <Button v-if="!ollama.installed" :disabled="ollamaInstalando" @click="instalarOllama">
          {{ ollamaInstalando ? 'Instalando…' : 'Instalar Ollama' }}
        </Button>
        <Button variant="secondary" @click="checarOllama">Verificar de novo</Button>
      </div>
      <p v-if="ollamaManual" class="mt-2 text-xs text-amber-700 dark:text-amber-400">
        Rode no terminal: <code class="rounded bg-amber-100 px-1 dark:bg-amber-900/50">{{ ollamaManual }}</code>
      </p>
    </div>
    <p v-else-if="ollama" class="text-sm font-medium text-green-600 dark:text-green-400">✓ Ollama pronto</p>

    <!-- Componentes -->
    <Card title="Componentes" subtitle="Baixe o que falta. Re-baixar é seguro (idempotente).">
      <template #header>
        <Button variant="secondary" :disabled="baixandoTudo" @click="baixarTudo">
          {{ baixandoTudo ? 'Baixando…' : 'Baixar tudo' }}
        </Button>
      </template>
      <div class="space-y-2">
        <DownloadableItem
          v-for="c in componentes"
          :key="c.kind"
          :title="c.title"
          :tag="c.tag"
          :subtitle="c.subtitle"
          :state="estado(c.kind).state"
          :pct="estado(c.kind).pct"
          :error="estado(c.kind).error"
          @download="baixar(c)"
        />
      </div>
    </Card>

    <!-- Salvar -->
    <div class="flex items-center justify-between">
      <p v-if="resultado" class="text-sm" :class="resultado.ok ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'">
        {{ resultado.msg }}
      </p>
      <span v-else />
      <Button :disabled="salvando" @click="salvar">
        {{ salvando ? 'Salvando…' : store.editMode ? 'Salvar alterações' : 'Salvar e concluir' }}
      </Button>
    </div>
  </div>
</template>
