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

export interface DeviceInfo {
  name: string
}

export interface VoiceCatalog {
  oficiais: { nome: string; desc: string }[]
  comunidade: { nome: string }[]
  instaladas: string[]
  default: string
}

export type ComponentKind = 'llm' | 'stt' | 'tts_voice' | 'rag_embedder'

export interface ComponentStatus {
  kind: ComponentKind
  key: string
  installed: boolean | null // null = idempotente/desconhecido (STT/embedding)
}

export interface DownloadResult {
  ok: boolean
  kind: string
  key: string
  msg?: string
  path?: string | null
}

// Empurrado pelo Python via window.__antaProgress durante download_component.
export interface ProgressEvent {
  kind: string
  key: string
  phase: 'start' | 'line' | 'done' | 'error'
  text?: string
  pct?: number | null
}

export interface TestResult {
  ok: boolean
  msg?: string
  pico?: number
  rms?: number
}

export interface HotkeyValidation {
  valid: boolean
  normalized: string
  msg: string
}

export interface SaveResult {
  ok: boolean
  path?: string
  warnings?: string[]
  msg?: string
}

// Facade tipada. Os nomes camelCase mapeiam para os metodos snake_case do Python.
export interface ConfigApiFacade {
  ping(): Promise<string>
  echo(value: unknown): Promise<unknown>
  getEnvironment(): Promise<EnvInfo>
  getHardware(): Promise<Hardware>
  getCatalog(): Promise<Catalog>
  getConfig(): Promise<UserConfig>
  listMicrophones(): Promise<DeviceInfo[]>
  listSpeakers(): Promise<DeviceInfo[]>
  listVoices(): Promise<VoiceCatalog>
  componentStatus(kind: ComponentKind, key: string): Promise<ComponentStatus>
  downloadComponent(kind: ComponentKind, key: string): Promise<DownloadResult>
  testMicrophone(device?: string | null, seconds?: number): Promise<TestResult>
  testTts(voice?: string | null, device?: string | null, text?: string): Promise<TestResult>
  testModelLoad(family: string, mode: string): Promise<TestResult>
  validateHotkey(hotkey: string): Promise<HotkeyValidation>
  save(cfg: Partial<UserConfig>): Promise<SaveResult>
}
