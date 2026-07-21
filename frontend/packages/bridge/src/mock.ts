// Mock da API para desenvolver a UI num browser puro (sem pywebview).
// Dados de exemplo, com forma identica ao que o Python devolve.

import type { Catalog, EnvInfo, Hardware, UserConfig } from './types'

const MOCK_HARDWARE: Hardware = {
  gpus: [{ name: '(mock) sem GPU NVIDIA', vram_gb: 0 }],
  best_vram_gb: 0,
  ram_gb: 16,
  disk_free_gb: 200,
}

// Amostra enxuta do catalogo (o Python devolve o modes.yaml completo).
const MOCK_CATALOG: Catalog = {
  best_vram_gb: 0,
  families: [
    {
      key: 'qwen3',
      label: 'Qwen3',
      structured: 'json_schema',
      modes: [
        {
          key: 'batata', label: 'Batata', vram_gb: 1, vram_real: '~1 GB',
          llm: 'qwen3:0.6b', stt: 'base', description: 'Cabe em qualquer maquina.',
          structured: 'json_schema', status: 'vermelho',
        },
        {
          key: 'leve', label: 'Leve', vram_gb: 4, vram_real: '~4 GB',
          llm: 'qwen3:4b-instruct', stt: 'turbo', description: 'Equilibrio bom.',
          structured: 'json_schema', status: 'vermelho',
        },
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
    default:
      throw new Error(`[bridge mock] metodo desconhecido: ${name}`)
  }
}
