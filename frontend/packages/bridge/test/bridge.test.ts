import { afterEach, describe, expect, it, vi } from 'vitest'
import { callApi, configApi, hasPywebview, onState, runtimeApi, setReadyTimeoutMs } from '../src'

type Win = typeof window & { pywebview?: { api?: Record<string, unknown> } }

afterEach(() => {
  delete (window as Win).pywebview
  setReadyTimeoutMs(1000)
})

describe('callApi', () => {
  it('usa a api real do pywebview quando presente', async () => {
    const spy = vi.fn().mockResolvedValue('real')
    ;(window as Win).pywebview = { api: { get_hardware: spy } }
    const r = await callApi('get_hardware', 1, 2)
    expect(r).toBe('real')
    expect(spy).toHaveBeenCalledWith(1, 2)
  })

  it('aguarda o evento pywebviewready antes de resolver', async () => {
    setReadyTimeoutMs(2000) // maior que o atraso da injecao, p/ nao cair no mock
    const spy = vi.fn().mockResolvedValue('depois')
    const pending = callApi('ping')
    setTimeout(() => {
      ;(window as Win).pywebview = { api: { ping: spy } }
      window.dispatchEvent(new Event('pywebviewready'))
    }, 10)
    await expect(pending).resolves.toBe('depois')
    expect(spy).toHaveBeenCalled()
  })

  it('cai no mock quando nao ha pywebview (browser puro)', async () => {
    setReadyTimeoutMs(5) // carencia curta p/ teste rapido
    await expect(callApi('ping')).resolves.toBe('pong (mock)')
  })

  it('o mock lanca em metodo desconhecido', async () => {
    setReadyTimeoutMs(5)
    await expect(callApi('nao_existe')).rejects.toThrow(/desconhecido/)
  })
})

describe('configApi (facade)', () => {
  it('mapeia camelCase -> snake_case (getHardware -> get_hardware)', async () => {
    const spy = vi.fn().mockResolvedValue({ best_vram_gb: 8 })
    ;(window as Win).pywebview = { api: { get_hardware: spy } }
    const hw = await configApi.getHardware()
    expect(spy).toHaveBeenCalled()
    expect(hw.best_vram_gb).toBe(8)
  })

  it('getCatalog no browser puro devolve o mock', async () => {
    setReadyTimeoutMs(5)
    const cat = await configApi.getCatalog()
    expect(cat.families[0].key).toBe('qwen3')
  })
})

describe('hasPywebview', () => {
  it('reflete a presenca da api', () => {
    expect(hasPywebview()).toBe(false)
    ;(window as Win).pywebview = { api: {} }
    expect(hasPywebview()).toBe(true)
  })
})

describe('runtimeApi + onState', () => {
  it('getState mapeia para get_state', async () => {
    const spy = vi.fn().mockResolvedValue({ state: 'pronto' })
    ;(window as Win).pywebview = { api: { get_state: spy } }
    const r = await runtimeApi.getState()
    expect(spy).toHaveBeenCalled()
    expect(r.state).toBe('pronto')
  })

  it('onState registra window.__antaOnState e o unsubscribe remove', () => {
    const w = window as unknown as { __antaOnState?: (e: unknown) => void }
    const cb = vi.fn()
    const off = onState(cb as never)
    w.__antaOnState?.({ state: 'ouvindo' })
    expect(cb).toHaveBeenCalledWith({ state: 'ouvindo' })
    off()
    expect(w.__antaOnState).toBeUndefined()
  })

  it('cancel mapeia para cancel (metodo proprio, nao um toggle)', async () => {
    const spy = vi.fn().mockResolvedValue({ ok: true })
    ;(window as Win).pywebview = { api: { cancel: spy } }
    await runtimeApi.cancel()
    expect(spy).toHaveBeenCalled()
  })

  it('getMemory mapeia para get_memory', async () => {
    const spy = vi.fn().mockResolvedValue({ vram_used_gb: 5.2 })
    ;(window as Win).pywebview = { api: { get_memory: spy } }
    const m = await runtimeApi.getMemory()
    expect(m.vram_used_gb).toBe(5.2)
  })
})

describe('mock do HUD (dev no browser)', () => {
  // O mock e o unico jeito de exercitar o HUD sem Python; ele tem que ROTEAR como
  // o Session.request(), senao a UI e desenvolvida contra um comportamento que nao existe.
  it('toggle durante a resposta para, em vez de gravar de novo', async () => {
    setReadyTimeoutMs(5)
    const eventos: string[] = []
    const off = onState(((e: { state: string }) => eventos.push(e.state)) as never)
    await runtimeApi.toggle() // pronto -> ouvindo
    await runtimeApi.toggle() // ouvindo -> processando
    await runtimeApi.toggle() // processando -> PARA (nao volta a ouvir)
    off()
    expect(eventos).toEqual(['ouvindo', 'processando', 'pronto'])
  })

  it('desalocado ignora o gatilho ate carregar', async () => {
    setReadyTimeoutMs(5)
    await runtimeApi.unloadModel()
    const eventos: string[] = []
    const off = onState(((e: { state: string }) => eventos.push(e.state)) as never)
    await runtimeApi.toggle()
    off()
    expect(eventos).toEqual([])
    await runtimeApi.loadModel() // volta ao normal p/ os outros testes
  })
})
