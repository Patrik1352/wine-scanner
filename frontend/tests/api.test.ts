import { afterEach, describe, expect, it, vi } from 'vitest'
import { readFileSync } from 'node:fs'
import { createService, parseRecognition, parseWine, alternativeReasons, httpError, safeUrl } from '../app/services/api'
import { isHeic, preparePhoto, validateFile, validatePhoto, cameraError, reasonHints } from '../app/services/photo'
const cards = JSON.parse(readFileSync('public/demo/cards.json', 'utf8'))
const signal = () => new AbortController().signal
const photo = () => new File(['photo'], 'any-name.jpg', { type: 'image/jpeg' })
afterEach(() => { vi.unstubAllGlobals(); vi.useRealTimers() })
describe('Product contract', () => {
  it('accepts only consistent recognition outcomes', () => {
    expect(parseRecognition({ status: 'matched', slug: 'wine', confidence: .91 })).toEqual({ status: 'matched', slug: 'wine' })
    expect(parseRecognition({ status: 'matched', slug: 'wine', confidence: .2, low_confidence: true })).toEqual({ status: 'matched', slug: 'wine', low_confidence: true })
    expect(() => parseRecognition({ status: 'matched', slug: 'wine', low_confidence: 'yes' })).toThrow()
    for (const status of ['needs_better_photo', 'no_confident_match']) {
      expect(parseRecognition({ status, slug: null, reason_code: 'low_quality' }).slug).toBeNull()
      expect(() => parseRecognition({ status, slug: 'wine', reason_code: 'x' })).toThrow()
      expect(() => parseRecognition({ status, slug: null })).toThrow()
    }
    expect(() => parseRecognition({ status: 'matched', slug: null })).toThrow()
  })
  it('preserves missing values and separate ratings, rejects malformed lists', () => {
    const missing = parseWine(cards[4]); expect(missing.public_rating).toBeNull(); expect(missing.alcohol_percent).toBeNull(); expect(missing.food_pairings).toEqual([])
    const full = parseWine(cards[1]); expect(full.public_rating).toBe(5); expect(full.guide_rating).toBe(4.33)
    expect(() => parseWine({ slug: 'a', name: 'a', grapes: [1] })).toThrow()
    expect(() => parseWine({ slug: 'a', name: 'a', public_rating: '5' })).toThrow()
  })
  it('filters unsafe URLs, resolves backend images', () => {
    expect(safeUrl('javascript:alert(1)')).toBeNull()
    expect(safeUrl('/uploads/a.webp','https://api.example.test/')).toBe('https://api.example.test/uploads/a.webp')
  })
  it('uses ready + multipart image + encoded wine slug, does not set multipart headers', async () => {
    const fetch = vi.fn().mockResolvedValueOnce(new Response(null, { status: 204 })).mockResolvedValueOnce(Response.json({ status: 'matched', slug: cards[0].slug })).mockResolvedValueOnce(Response.json(cards[0]))
    vi.stubGlobal('fetch', fetch)
    const api = createService('api','https://api.example.test/', 'matched'); const s = signal()
    await api.ready(s); const result = await api.recognize(photo(),s); await api.wine(result.slug!,s)
    expect(fetch.mock.calls[0]![0]).toBe('https://api.example.test/health/ready')
    expect(fetch.mock.calls[1]![0]).toBe('https://api.example.test/v1/recognize')
    const options = fetch.mock.calls[1]![1]
    expect(options.body.get('image').name).toBe('any-name.jpg'); expect(options.headers).toBeUndefined()
    expect(fetch.mock.calls[2]![0]).toBe('https://api.example.test/v1/wines/'+cards[0].slug)
  })
  it('rejects wrong-slug cards and non-JSON responses', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValueOnce(Response.json(cards[0])).mockResolvedValueOnce(new Response('<html>')))
    const api = createService('api','', 'matched')
    await expect(api.wine('other',signal())).rejects.toThrow('другая карточка')
    await expect(api.recognize(photo(),signal())).rejects.toThrow('неизвестном формате')
  })
  it('maps errors without pretending no match', async () => {
    expect(httpError(413).code).toBe('size'); expect(httpError(415).code).toBe('format'); expect(httpError(503).code).toBe('unavailable')
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')))
    await expect(createService('api','', 'matched').recognize(photo(),signal())).rejects.toMatchObject({code:'offline'})
  })
})
describe('Explicit demonstration', () => {
  it('uses the scenario regardless of the photo name or bytes', async () => {
    vi.useFakeTimers()
    for (const name of ['bottle.jpg', 'unrelated.jpg']) {
      const promise = createService('demo','', 'ratings').recognize(new File([name],name),signal())
      await vi.runAllTimersAsync(); expect((await promise).slug).toBe(cards[1].slug)
    }
  })
  it.each(['low_quality','multiple_bottles','ambiguous_pair','no_confident_match'] as const)('returns nullable slug for %s', async scenario => {
    vi.useFakeTimers(); const promise = createService('demo','',scenario).recognize(photo(),signal())
    await vi.runAllTimersAsync(); const result = await promise
    expect(result.slug).toBeNull(); expect(result.status).not.toBe('matched')
    if (result.status !== 'matched') expect(reasonHints[result.reason_code]).toBeTruthy()
  })
  it('only explains alternatives with actual common fields', () => {
    const wine = parseWine(cards[0]); const other = parseWine(cards[1])
    expect(alternativeReasons(wine,other)).toEqual(['Та же категория: белое сухое','Общие сорта: Шардоне'])
    expect(alternativeReasons(wine,parseWine({slug:'unknown',name:'Unknown'}))).toEqual([])
  })
})
describe('Photos and camera', () => {
  it('identifies HEIC for conversion and rejects empty files and files over 15 MiB', () => {
    expect(isHeic(new File(['a'],'a.heic',{type:'image/heic'}))).toBe(true)
    expect(isHeic(new File(['a'],'a.HEIF',{type:''}))).toBe(true)
    expect(isHeic(photo())).toBe(false)
    expect(() => validateFile(new File([],'a.jpg',{type:'image/jpeg'}))).toThrow('пустой')
    expect(() => validateFile(new File([new Uint8Array(15*1024*1024+1)],'a.jpg',{type:'image/jpeg'}))).toThrow('большая')
    expect(() => validateFile(photo())).not.toThrow()
  })
  it('detects HEIC bytes even if iPhone reports the file as JPEG', async () => {
    const source = new File([new Uint8Array([0, 0, 0, 24, 0x66, 0x74, 0x79, 0x70, 0x68, 0x65, 0x69, 0x66])], 'iphone.jpg', { type: 'image/jpeg' })
    await expect(preparePhoto(source)).rejects.toThrow('преобразовать HEIC')
  })
  it('checks decoded dimensions and corrupt image data', async () => {
    vi.stubGlobal('Image', class { naturalWidth=6000; naturalHeight=6000; onload=()=>{}; set src(_v:string){this.onload()} })
    await expect(validatePhoto(photo(),'blob:test')).rejects.toThrow('30 мегапикселей')
    vi.stubGlobal('Image', class { onerror=()=>{}; set src(_v:string){this.onerror()} })
    await expect(validatePhoto(photo(),'blob:test')).rejects.toThrow('повреждён')
  })
  it('gives actionable camera denial and missing device messages', () => {
    expect(cameraError(new DOMException('denied','NotAllowedError'))).toContain('Разрешите')
    expect(cameraError(new DOMException('missing','NotFoundError'))).toContain('не найдена')
  })
})
