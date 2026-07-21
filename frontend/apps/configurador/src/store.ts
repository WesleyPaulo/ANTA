import { reactive } from 'vue'
import {
  configApi,
  type Catalog, type DeviceInfo, type EnvInfo, type FamilyInfo, type Hardware,
  type ModeInfo, type ProgressEvent, type UserConfig, type VoiceCatalog,
} from '@anta/bridge'

type Form = {
  family: string
  mode: string
  mic_device: string | null
  tts: boolean
  tts_voice: string | null
  tts_output: string | null
  hotkey: string
  obsidian_vault: string | null
  rag: boolean
  web: boolean
  web_engine: string
  web_searxng_url: string | null
}

type ItemProgress = { phase: string; pct: number | null; text: string }

export const store = reactive({
  loading: true,
  loaded: false,
  error: null as string | null,
  editMode: false, // config já existe -> passos viram abas livres

  hardware: null as Hardware | null,
  catalog: null as Catalog | null,
  environment: null as EnvInfo | null,
  microphones: [] as DeviceInfo[],
  speakers: [] as DeviceInfo[],
  voices: null as VoiceCatalog | null,

  form: {
    family: 'qwen3', mode: 'leve', mic_device: null, tts: false, tts_voice: null,
    tts_output: null, hotkey: 'ctrl+alt+space', obsidian_vault: null, rag: true,
    web: false, web_engine: 'duckduckgo', web_searxng_url: null,
  } as Form,

  progress: {} as Record<string, ItemProgress>,

  async init() {
    if (this.loaded) return
    this.loading = true
    this.error = null
    // Progresso empurrado pelo Python (ou pelo mock) durante download_component.
    ;(window as unknown as { __antaProgress?: (p: ProgressEvent) => void }).__antaProgress = (p) => {
      store.progress[p.kind] = { phase: p.phase, pct: p.pct ?? null, text: p.text ?? '' }
    }
    try {
      const [hw, cat, env, cfg, mics, spk, voices] = await Promise.all([
        configApi.getHardware(),
        configApi.getCatalog(),
        configApi.getEnvironment(),
        configApi.getConfig(),
        configApi.listMicrophones(),
        configApi.listSpeakers(),
        configApi.listVoices(),
      ])
      this.hardware = hw
      this.catalog = cat
      this.environment = env
      this.microphones = mics
      this.speakers = spk
      this.voices = voices
      this.seedForm(cfg)
      this.editMode = cfg.configured
      this.loaded = true
    } catch (e) {
      this.error = `Não consegui carregar o backend (${String(e)}). ` +
        'Abra pela janela do "anta config".'
    } finally {
      this.loading = false
    }
  },

  seedForm(cfg: UserConfig) {
    this.form.family = cfg.family
    this.form.mode = cfg.mode
    this.form.mic_device = cfg.mic_device
    this.form.tts = cfg.tts
    this.form.tts_voice = cfg.tts_voice
    this.form.tts_output = cfg.tts_output
    this.form.hotkey = cfg.hotkey
    this.form.obsidian_vault = cfg.obsidian_vault
    this.form.rag = cfg.rag
    this.form.web = cfg.web
    this.form.web_engine = cfg.web_engine
    this.form.web_searxng_url = cfg.web_searxng_url
  },

  family(): FamilyInfo | null {
    return this.catalog?.families.find((f) => f.key === this.form.family) ?? null
  },

  mode(): ModeInfo | null {
    return this.family()?.modes.find((m) => m.key === this.form.mode) ?? null
  },

  // Ao trocar de família, garante que o modo escolhido existe nela.
  setFamily(key: string) {
    this.form.family = key
    const fam = this.family()
    if (fam && !fam.modes.some((m) => m.key === this.form.mode)) {
      this.form.mode = fam.modes[0]?.key ?? this.form.mode
    }
  },

  toConfig(): Form {
    return { ...this.form }
  },
})
