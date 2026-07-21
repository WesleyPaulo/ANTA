import { afterEach, describe, expect, it, vi } from 'vitest'
import { callApi, configApi, hasPywebview, setReadyTimeoutMs } from '../src'

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
