// Mock da API para desenvolver a UI num browser puro (sem pywebview).
// Dados de exemplo, com forma identica ao que o Python devolve.

import type {
  Catalog, DeviceInfo, EnvInfo, Hardware, RuntimeState, SaveResult, StateEvent,
  UserConfig, VoiceCatalog,
} from './types'

const MOCK_HARDWARE: Hardware = {
  gpus: [{ name: '(mock) sem GPU NVIDIA', vram_gb: 0 }],
  best_vram_gb: 8, // finge 8GB p/ a UI mostrar modos verdes/amarelos/vermelhos
  ram_gb: 16,
  disk_free_gb: 200,
}

function modo(
  key: string, label: string, vram: number, llm: string, stt: string, desc: string,
): Catalog['families'][number]['modes'][number] {
  const best = MOCK_HARDWARE.best_vram_gb
  const status = best >= vram ? 'verde' : best >= vram - 1 ? 'amarelo' : 'vermelho'
  return {
    key, label, vram_gb: vram, vram_real: `~${vram} GB`, llm, stt, description: desc,
    structured: 'json_schema', status,
  }
}

const MOCK_CATALOG: Catalog = {
  best_vram_gb: MOCK_HARDWARE.best_vram_gb,
  families: [
    {
      key: 'qwen3', label: 'Qwen3', structured: 'json_schema',
      modes: [
        modo('batata', 'Batata', 1, 'qwen3:0.6b', 'base', 'Cabe em qualquer maquina.'),
        modo('leve', 'Leve', 4, 'qwen3:4b-instruct', 'turbo', 'Equilibrio bom.'),
        modo('normal', 'Normal', 6, 'qwen3:4b-instruct', 'large-v3', 'Mais folga.'),
        modo('pesado', 'Pesado', 8, 'qwen3:8b', 'large-v3', 'Respostas melhores.'),
        modo('ultra', 'Ultra', 12, 'qwen3:14b', 'large-v3', 'Topo da familia.'),
      ],
    },
    {
      key: 'gemma', label: 'Gemma', structured: 'json_schema',
      modes: [
        modo('leve', 'Leve', 4, 'gemma3:4b', 'turbo', 'Equilibrio bom.'),
        modo('muito-pesado', 'Muito Pesado', 10, 'gemma3:12b', 'large-v3', 'Bem capaz.'),
      ],
    },
  ],
}

const MOCK_ENV: EnvInfo = {
  os: '(mock) Browser', session: 'n/a', desktop: 'n/a', is_wayland: false,
  hotkey_strategy: 'manual', captures_hotkey_in_process: false,
}

const MOCK_CONFIG: UserConfig = {
  mode: 'leve', family: 'qwen3', mic_device: null, hotkey: 'ctrl+alt+space',
  obsidian_vault: null, tts: false, tts_voice: null, tts_output: null,
  rag: true, web: false, web_engine: 'duckduckgo', web_searxng_url: null,
  schema_version: 1, configured: false,
}

const MOCK_MICS: DeviceInfo[] = [{ name: 'USB Mic (mock)' }, { name: 'Webcam (mock)' }]
const MOCK_SPEAKERS: DeviceInfo[] = [{ name: 'Alto-falantes (mock)' }, { name: 'Fone BT (mock)' }]

const MOCK_VOICES: VoiceCatalog = {
  oficiais: [
    { nome: 'pt_BR-faber-medium', desc: 'Masculina, clara (padrao)' },
    { nome: 'pt_BR-cadu-medium', desc: 'Masculina' },
    { nome: 'pt_BR-edresson-low', desc: 'Feminina, leve' },
  ],
  comunidade: [{ nome: 'pt_BR-dii-high' }, { nome: 'pt_BR-miro-high' }],
  instaladas: [],
  default: 'pt_BR-faber-medium',
}

function emitProgress(kind: string, key: string) {
  // Simula o window.__antaProgress que o Python empurraria durante o download.
  const w = window as unknown as { __antaProgress?: (p: unknown) => void }
  const send = (phase: string, pct: number | null, text: string) =>
    w.__antaProgress?.({ kind, key, phase, pct, text })
  send('start', null, `Baixando ${key}...`)
  let pct = 0
  const timer = setInterval(() => {
    pct += 25
    if (pct >= 100) {
      clearInterval(timer)
      send('done', 100, 'concluido (mock)')
    } else {
      send('line', pct, `pulling ${pct}%`)
    }
  }, 120)
}

// --- runtime (HUD): estado simulado + eventos via window.__antaOnState ---
let mockState: RuntimeState = 'pronto'

function pushState(state: RuntimeState, extra?: Partial<StateEvent>) {
  mockState = state
  const w = window as unknown as { __antaOnState?: (ev: StateEvent) => void }
  w.__antaOnState?.({ state, ...extra })
}

function simulateToggle() {
  if (mockState === 'ouvindo') return // ja ouvindo: ignora
  pushState('ouvindo')
  setTimeout(() => pushState('processando'), 900)
  setTimeout(() => pushState('respondendo', { text: 'responder' }), 1600)
  setTimeout(() => pushState('pronto'), 2600)
}

export async function callMock<T = unknown>(name: string, ...args: unknown[]): Promise<T> {
  switch (name) {
    case 'ping':
      return 'pong (mock)' as T
    case 'echo':
      return args[0] as T
    case 'get_environment':
      return MOCK_ENV as T
    case 'get_hardware':
      return MOCK_HARDWARE as T
    case 'get_catalog':
      return MOCK_CATALOG as T
    case 'get_config':
      return MOCK_CONFIG as T
    case 'list_microphones':
      return MOCK_MICS as T
    case 'list_speakers':
      return MOCK_SPEAKERS as T
    case 'list_voices':
      return MOCK_VOICES as T
    case 'component_status':
      return { kind: args[0], key: args[1], installed: false } as T
    case 'download_component': {
      const [kind, key] = args as [string, string]
      emitProgress(kind, key)
      return new Promise<T>((resolve) =>
        setTimeout(() => resolve({ ok: true, kind, key } as T), 560),
      )
    }
    case 'test_microphone':
      return { ok: true, pico: 0.42, rms: 0.12 } as T
    case 'test_tts':
      return { ok: true } as T
    case 'test_model_load':
      return { ok: true, msg: '' } as T
    case 'validate_hotkey': {
      const hk = String(args[0] ?? '')
      const valid = hk.includes('+') && !hk.endsWith('+')
      return { valid, normalized: valid ? hk.toLowerCase() : '', msg: valid ? '' : 'Atalho invalido.' } as T
    }
    case 'ollama_status':
      return { installed: true, running: true } as T
    case 'install_ollama':
      return { ok: true } as T
    case 'save':
      return { ok: true, path: '(mock)/config.toml', warnings: [] } as SaveResult as T
    case 'get_state':
      return { state: mockState } as T
    case 'toggle':
      simulateToggle()
      return undefined as T
    case 'load_model':
      pushState('carregando')
      setTimeout(() => pushState('pronto'), 900)
      return { ok: true, msg: '' } as T
    case 'unload_model':
      pushState('descarregado')
      return { ok: true, msg: '' } as T
    case 'open_configurador':
      return { ok: true } as T
    case 'hide':
    case 'show':
      return undefined as T
    default:
      throw new Error(`[bridge mock] metodo desconhecido: ${name}`)
  }
}
