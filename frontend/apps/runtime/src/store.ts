import { reactive } from 'vue'
import { onState, runtimeApi, type RuntimeState, type UserConfig } from '@anta/bridge'

// A maquina de estados de verdade vive no backend (Python). O HUD so REFLETE:
// assina window.__antaOnState e pinta o estado atual (guia §5).
export const store = reactive({
  state: 'carregando' as RuntimeState,
  code: '' as string,
  resposta: '' as string, // ultima resposta (texto) — persiste ate a proxima fala
  erro: '' as string, // detalhe do ultimo erro
  config: null as UserConfig | null,
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
    })
    // snapshot no mount evita corrida (a janela pode nascer antes da 1a transicao)
    try {
      const [s, cfg] = await Promise.all([runtimeApi.getState(), runtimeApi.getConfig()])
      store.state = s.state
      store.config = cfg
    } catch {
      /* sem backend (mock/erro): fica no estado inicial */
    }
  },

  toggle() {
    runtimeApi.toggle()
  },

  async unload() {
    store.busy = true
    try {
      await runtimeApi.unloadModel()
    } finally {
      store.busy = false
    }
  },

  async load() {
    store.busy = true
    try {
      await runtimeApi.loadModel()
    } finally {
      store.busy = false
    }
  },

  openConfigurador() {
    runtimeApi.openConfigurador()
  },
})
