import type { Wine, Recognition, WineService, DemoScenario, Mode } from './types'

export class ServiceError extends Error {
  constructor(public code: string, message: string) { super(message) }
}
const textFields = ['winery_name', 'region', 'category', 'color_category', 'sweetness_from_category', 'description', 'serving_temperature_c', 'source_url', 'fetched_at'] as const
const numberFields = ['alcohol_percent', 'alcohol_max_percent', 'public_rating', 'guide_rating'] as const
const listFields = ['grapes', 'food_pairings', 'similar_wine_slugs'] as const
function record(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== 'object' || Array.isArray(value)) throw new ServiceError('contract', 'Сервис вернул ответ в неизвестном формате.')
  return value as Record<string, unknown>
}
export function safeUrl(value: unknown, base?: string): string | null {
  if (typeof value !== 'string' || !value.trim()) return null
  try {
    const url = new URL(value, base || 'http://localhost')
    if (!['http:', 'https:'].includes(url.protocol)) return null
    return value.startsWith('/') && !value.startsWith('//') && !base ? value : url.href
  } catch { return null }
}
export function parseWine(value: unknown, base?: string): Wine {
  const raw = record(value)
  if (typeof raw.slug !== 'string' || !raw.slug.trim() || typeof raw.name !== 'string' || !raw.name.trim()) throw new ServiceError('contract', 'В карточке нет названия или идентификатора вина.')
  const wine = { slug: raw.slug, name: raw.name, image_url: safeUrl(raw.image_url, base) } as Wine
  for (const key of textFields) {
    const v = raw[key]
    if (v != null && typeof v !== 'string') throw new ServiceError('contract', 'Неверный формат сведений о вине.')
    wine[key] = typeof v === 'string' && v.trim() ? v : null
  }
  wine.source_url = safeUrl(wine.source_url, base)
  for (const key of numberFields) {
    const v = raw[key]
    if (v != null && (typeof v !== 'number' || !Number.isFinite(v))) throw new ServiceError('contract', 'Неверный формат показателей вина.')
    wine[key] = v == null ? null : v as number
  }
  for (const key of listFields) {
    const v = raw[key]
    if (v != null && (!Array.isArray(v) || v.some(x => typeof x !== 'string'))) throw new ServiceError('contract', 'Неверный формат списка в карточке.')
    wine[key] = ((v ?? []) as string[]).filter(x => x.trim())
  }
  return wine
}
export function parseRecognition(value: unknown): Recognition {
  const raw = record(value)
  if (raw.status === 'matched' && typeof raw.slug === 'string' && raw.slug.trim()) {
    if (raw.low_confidence != null && typeof raw.low_confidence !== 'boolean') throw new ServiceError('contract', 'Сервис вернул противоречивый результат. Попробуйте ещё раз.')
    return { status: 'matched', slug: raw.slug, ...(raw.low_confidence === true ? { low_confidence: true } : {}) }
  }
  if (['needs_better_photo', 'no_confident_match'].includes(String(raw.status)) && raw.slug === null && typeof raw.reason_code === 'string' && raw.reason_code.trim()) return { status: raw.status as 'needs_better_photo' | 'no_confident_match', slug: null, reason_code: raw.reason_code }
  throw new ServiceError('contract', 'Сервис вернул противоречивый результат. Попробуйте ещё раз.')
}
export function httpError(status: number): ServiceError {
  if (status === 413) return new ServiceError('size', 'Фотография слишком большая. Выберите файл до 15 МБ и 30 мегапикселей.')
  if ([400, 415, 422].includes(status)) return new ServiceError('format', 'Сервис не смог прочитать фото. Выберите JPEG, PNG или WebP.')
  if (status === 404) return new ServiceError('missing', 'Карточка вина пока недоступна. Попробуйте позже.')
  return new ServiceError('unavailable', 'Сервис временно недоступен. Попробуйте ещё раз немного позже.')
}
async function request(url: string, signal: AbortSignal, options: RequestInit = {}): Promise<unknown> {
  let response: Response
  try { response = await fetch(url, { ...options, signal }) }
  catch (error) {
    if (signal.aborted) throw error
    throw new ServiceError('offline', 'Не удалось связаться с сервисом. Проверьте подключение и попробуйте ещё раз.')
  }
  if (!response.ok) throw httpError(response.status)
  try { return await response.json() } catch { throw new ServiceError('contract', 'Сервис вернул ответ в неизвестном формате.') }
}
const slugs = {
  matched: 'fanagoriya-cru-lermont-chardonnay-shardone-beloe-suhoe-14',
  ratings: 'usadba-markoth-shardone-beloe-suhoe-12',
  incomplete: 'abrau-dyurso-abrau-kupazh-svetlyy-suhoe-shardone-beloe-125'
}
export async function demoCards(signal: AbortSignal): Promise<Wine[]> {
  const data = await request('/demo/cards.json', signal)
  if (!Array.isArray(data)) throw new ServiceError('contract', 'Не удалось загрузить демонстрационные карточки.')
  return data.map(x => parseWine(x))
}
export function alternativeReasons(source: Wine, candidate: Wine): string[] {
  const reasons: string[] = []
  if (source.category && source.category === candidate.category) reasons.push(`Та же категория: ${candidate.category.toLocaleLowerCase('ru')}`)
  const grapes = candidate.grapes.filter(x => source.grapes.includes(x))
  if (grapes.length) reasons.push(`Общие сорта: ${grapes.join(', ')}`)
  const food = candidate.food_pairings.filter(x => source.food_pairings.includes(x))
  if (food.length) reasons.push(`Также к блюдам: ${food.join(', ').toLocaleLowerCase('ru')}`)
  if (!reasons.length && source.similar_wine_slugs.includes(candidate.slug)) reasons.push('Похожее вино по рекомендации каталога «Своё Вино»')
  return reasons
}
export function createService(mode: Mode, apiBase: string, scenario: DemoScenario): WineService {
  const base = apiBase.replace(/\/+$/, '')
  const api = (path: string, signal: AbortSignal, options?: RequestInit) => request(base + path, signal, options)
  const wine = async (slug: string, signal: AbortSignal): Promise<Wine> => {
    const result = mode === 'demo' ? (await demoCards(signal)).find(w => w.slug === slug) : parseWine(await api(`/v1/wines/${encodeURIComponent(slug)}`, signal), base ? base + '/' : undefined)
    if (!result || result.slug !== slug) throw new ServiceError('contract', 'Получена другая карточка вина. Повторите запрос.')
    return result
  }
  return {
    async ready(signal) {
      if (mode === 'demo') return
      // Readiness is conveyed by HTTP status, including 204; no JSON body required.
      let response: Response
      try { response = await fetch(base + '/health/ready', { signal }) }
      catch (e) { if (signal.aborted) throw e; throw new ServiceError('offline', 'Не удалось связаться с сервисом. Проверьте подключение.') }
      if (!response.ok) throw httpError(response.status === 404 ? 503 : response.status)
    },
    async recognize(file, signal) {
      if (mode === 'api') {
        const body = new FormData(); body.append('image', file)
        return parseRecognition(await api('/v1/recognize', signal, { method: 'POST', body }))
      }
      await new Promise<void>((resolve, reject) => {
        const abort = () => { clearTimeout(timer); reject(new DOMException('Aborted', 'AbortError')) }
        const timer = setTimeout(() => { signal.removeEventListener('abort', abort); resolve() }, 1400)
        if (signal.aborted) abort(); else signal.addEventListener('abort', abort, { once: true })
      })
      if (scenario === 'offline') throw new ServiceError('offline', 'Не удалось связаться с сервисом. Проверьте подключение и попробуйте ещё раз.')
      if (scenario === 'unavailable') throw httpError(503)
      if (scenario in slugs) return { status: 'matched', slug: slugs[scenario as keyof typeof slugs] }
      return { status: scenario === 'no_confident_match' ? 'no_confident_match' : 'needs_better_photo', slug: null, reason_code: scenario === 'no_confident_match' ? 'low_match_score' : scenario }
    },
    wine,
    async alternatives(source, signal) {
      if (mode === 'demo') return (await demoCards(signal)).filter(w => w.slug !== source.slug && alternativeReasons(source, w).length).sort((a,b) => alternativeReasons(source,b).length - alternativeReasons(source,a).length).slice(0,3)
      const ids = [...new Set(source.similar_wine_slugs)].filter(s => s !== source.slug).slice(0,3)
      return Promise.all(ids.map(slug => wine(slug, signal)))
    }
  }
}
