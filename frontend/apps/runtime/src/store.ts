import { reactive } from 'vue'
import { onState, runtimeApi, type RuntimeState, type UserConfig } from '@anta/bridge'

// A maquina de estados de verdade vive no backend (Python). O HUD so REFLETE:
// assina window.__antaOnState e pinta o estado atual (guia §5).
export const store = reactive({
  state: 'carregando' as RuntimeState,
  text: '' as string,
  code: '' as string,
  config: null as UserConfig | null,
  busy: false,

  async init() {
    onState((ev) => {
      store.state = ev.state
      store.text = ev.text ?? ''
      store.code = ev.code ?? ''
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
