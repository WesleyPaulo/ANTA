// A ÚNICA costura de verdade (guia §3): em vez de fetch/axios, o front chama
// metodos Python expostos em window.pywebview.api.<metodo>(...) -> Promise.
//
// callApi() centraliza isso: aguarda o pywebview ficar pronto ('pywebviewready'),
// chama o metodo real e, se nao houver pywebview (browser puro), cai no mock —
// assim a UI se desenvolve sem subir o Python.

import { callMock } from './mock'
import type { ConfigApiFacade } from './types'

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
}

export * from './types'
