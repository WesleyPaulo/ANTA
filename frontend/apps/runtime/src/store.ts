import { reactive } from 'vue'
import { onState, runtimeApi, type MemoryInfo, type RuntimeState, type UserConfig } from '@anta/bridge'

// A maquina de estados de verdade vive no backend (Python). O HUD so REFLETE:
// assina window.__antaOnState e pinta o estado atual (guia §5).
export const store = reactive({
  state: 'carregando' as RuntimeState,
  code: '' as string,
  resposta: '' as string, // ultima resposta (texto) — persiste ate a proxima fala
  erro: '' as string, // detalhe do ultimo erro
  config: null as UserConfig | null,
  memoria: null as MemoryInfo | null,
  busy: false,

  async init() {
    onState((ev) => {
      store.state = ev.state
      store.code = ev.code ?? ''
      if (ev.state === 'ouvindo') {
        store.resposta = '' // nova fala: limpa a anterior
        store.erro = ''
      }
      if (ev.state === 'erro') store.erro = ev.text ?? ''
      if (ev.state === 'pronto' && ev.text) store.resposta = ev.text
      // carregar/desalocar muda a memoria na hora — nao espera o proximo tick
      if (ev.state === 'pronto' || ev.state === 'descarregado') store.refreshMemory()
    })
    // snapshot no mount evita corrida (a janela pode nascer antes da 1a transicao)
    try {
      const [s, cfg] = await Promise.all([runtimeApi.getState(), runtimeApi.getConfig()])
      store.state = s.state
      store.config = cfg
    } catch {
      /* sem backend (mock/erro): fica no estado inicial */
    }
    store.refreshMemory()
    // A ANTA fica residente com o Whisper na RAM e o LLM na VRAM: sem esse numero
    // na tela ela parece um processo parado consumindo memoria sem explicacao.
    setInterval(() => store.refreshMemory(), 10_000)
  },

  async refreshMemory() {
    try {
      store.memoria = await runtimeApi.getMemory()
    } catch {
      store.memoria = null // sem medicao: o HUD simplesmente omite a linha
    }
  },

  toggle() {
    runtimeApi.toggle()
  },

  // Parar/cancelar e um metodo PROPRIO (nao um toggle): se o turno terminar entre
  // o render e o clique, cancelar vira no-op — enquanto um toggle atrasado
  // comecaria uma gravacao que ninguem pediu.
  cancel() {
    runtimeApi.cancel()
  },

  async unload() {
    store.busy = true
    try {
      await runtimeApi.unloadModel()
    } finally {
      store.busy = false
      store.refreshMemory()
    }
  },

  async load() {
    store.busy = true
    try {
      await runtimeApi.loadModel()
    } finally {
      store.busy = false
      store.refreshMemory()
    }
  },

  openConfigurador() {
    runtimeApi.openConfigurador()
  },
})
