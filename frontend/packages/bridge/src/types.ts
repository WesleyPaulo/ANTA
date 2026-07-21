// Tipos do contrato Python <-> Vue. Espelham os dicts que a ConfigApi
// (anta/gui/bridge_config.py) devolve. Mantenha em sincronia com o Python.

export type Status = 'verde' | 'amarelo' | 'vermelho'

export interface GpuInfo {
  name: string
  vram_gb: number
}

export interface Hardware {
  gpus: GpuInfo[]
  best_vram_gb: number
  ram_gb: number
  disk_free_gb: number
}

export interface ModeInfo {
  key: string
  label: string
  vram_gb: number
  vram_real: string
  llm: string
  stt: string
  description: string
  structured: string
  status: Status
}

export interface FamilyInfo {
  key: string
  label: string
  structured: string
  modes: ModeInfo[]
}

export interface Catalog {
  best_vram_gb: number
  families: FamilyInfo[]
}

export interface EnvInfo {
  os: string
  session: string
  desktop: string
  is_wayland: boolean
  hotkey_strategy: string
  captures_hotkey_in_process: boolean
}

export interface UserConfig {
  mode: string
  family: string
  mic_device: string | null
  hotkey: string
  obsidian_vault: string | null
  tts: boolean
  tts_voice: string | null
  tts_output: string | null
  rag: boolean
  web: boolean
  web_engine: string
  web_searxng_url: string | null
  schema_version: number
  configured: boolean
}

// Facade tipada. Os nomes camelCase mapeiam para os metodos snake_case do Python.
export interface ConfigApiFacade {
  ping(): Promise<string>
  echo(value: unknown): Promise<unknown>
  getEnvironment(): Promise<EnvInfo>
  getHardware(): Promise<Hardware>
  getCatalog(): Promise<Catalog>
  getConfig(): Promise<UserConfig>
}
