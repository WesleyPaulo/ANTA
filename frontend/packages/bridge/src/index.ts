// A ÚNICA costura de verdade (guia §3): em vez de fetch/axios, o front chama
// metodos Python expostos em window.pywebview.api.<metodo>(...) -> Promise.
//
// callApi() centraliza isso: aguarda o pywebview ficar pronto ('pywebviewready'),
// chama o metodo real e, se nao houver pywebview (browser puro), cai no mock —
// assim a UI se desenvolve sem subir o Python.

import { callMock } from './mock'
import type { ConfigApiFacade, RuntimeApiFacade, StateEvent } from './types'

type PywebviewApi = Record<string, (...args: unknown[]) => Promise<unknown>>

// Janela de carencia antes de decidir que nao ha pywebview (browser puro).
// Ajustavel para testes rapidos via setReadyTimeoutMs().
let readyTimeoutMs = 1000

export function setReadyTimeoutMs(ms: number): void {
  readyTimeoutMs = ms
}

function currentApi(): PywebviewApi | null {
  if (typeof window === 'undefined') return null
  const w = window as unknown as { pywebview?: { api?: PywebviewApi } }
  return w.pywebview?.api ?? null
}

export function hasPywebview(): boolean {
  return currentApi() !== null
}

function waitForApi(): Promise<PywebviewApi | null> {
  const existing = currentApi()
  if (existing) return Promise.resolve(existing)
  if (typeof window === 'undefined') return Promise.resolve(null)
  return new Promise((resolve) => {
    let settled = false
    const finish = () => {
      if (settled) return
      settled = true
      window.removeEventListener('pywebviewready', onReady)
      resolve(currentApi())
    }
    const onReady = () => finish()
    // O pywebview injeta a api de forma assincrona e dispara este evento.
    window.addEventListener('pywebviewready', onReady, { once: true })
    // Browser puro: o evento nunca vem -> cai no mock apos a carencia.
    setTimeout(finish, readyTimeoutMs)
  })
}

// Chamada crua por NOME (snake_case, igual ao metodo Python). Sempre async e
// falivel — trate no chamador (guia §3/§7): nada de travar a UI.
export async function callApi<T = unknown>(name: string, ...args: unknown[]): Promise<T> {
  const api = await waitForApi()
  if (api && typeof api[name] === 'function') {
    return (await api[name](...args)) as T
  }
  return callMock<T>(name, ...args)
}

// Facade tipada: camelCase -> nome snake_case do Python.
export const configApi: ConfigApiFacade = {
  ping: () => callApi<string>('ping'),
  echo: (value) => callApi('echo', value),
  getEnvironment: () => callApi('get_environment'),
  getHardware: () => callApi('get_hardware'),
  getCatalog: () => callApi('get_catalog'),
  getConfig: () => callApi('get_config'),
  listMicrophones: () => callApi('list_microphones'),
  listSpeakers: () => callApi('list_speakers'),
  listVoices: () => callApi('list_voices'),
  componentStatus: (kind, key) => callApi('component_status', kind, key),
  downloadComponent: (kind, key) => callApi('download_component', kind, key),
  testMicrophone: (device = null, seconds = 2.0) => callApi('test_microphone', device, seconds),
  testTts: (voice = null, device = null, text) => callApi('test_tts', voice, device, text),
  testModelLoad: (family, mode) => callApi('test_model_load', family, mode),
  validateHotkey: (hotkey) => callApi('validate_hotkey', hotkey),
  ollamaStatus: () => callApi('ollama_status'),
  installOllama: () => callApi('install_ollama'),
  save: (cfg) => callApi('save', cfg),
}

// App de execucao: facade + assinatura de estados (window.__antaOnState).
export const runtimeApi: RuntimeApiFacade = {
  getState: () => callApi('get_state'),
  toggle: () => callApi('toggle'),
  loadModel: () => callApi('load_model'),
  unloadModel: () => callApi('unload_model'),
  getConfig: () => callApi('get_config'),
  listMicrophones: () => callApi('list_microphones'),
  listSpeakers: () => callApi('list_speakers'),
  openConfigurador: () => callApi('open_configurador'),
  hide: () => callApi('hide'),
  show: () => callApi('show'),
}

// Assina os eventos de estado que o Python empurra. Devolve um unsubscribe.
export function onState(cb: (ev: StateEvent) => void): () => void {
  const w = window as unknown as { __antaOnState?: (ev: StateEvent) => void }
  w.__antaOnState = cb
  return () => {
    if (w.__antaOnState === cb) delete w.__antaOnState
  }
}

export * from './types'
