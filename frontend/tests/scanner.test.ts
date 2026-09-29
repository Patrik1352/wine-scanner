import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { readFileSync } from 'node:fs'
import { useScanner } from '../app/composables/useScanner'
const cards = JSON.parse(readFileSync('public/demo/cards.json', 'utf8'))
const file = (name='a') => new File(['a'],name+'.jpg',{type:'image/jpeg'})
beforeEach(() => {
  vi.stubGlobal('Image', class {naturalWidth=100; naturalHeight=100; onload=()=>{}; set src(_v:string){this.onload()} })
  vi.spyOn(URL,'createObjectURL').mockImplementation(() => 'blob:photo')
  vi.spyOn(URL,'revokeObjectURL').mockImplementation(() => {})
})
afterEach(() => {vi.unstubAllGlobals();vi.useRealTimers()})
it('replacing photo invalidates an old response even when fetch ignores abort', async () => {
  let reply!: (response: Response) => void
  vi.stubGlobal('fetch',vi.fn().mockResolvedValueOnce(new Response(null,{status:204})).mockImplementationOnce(() => new Promise(resolve=>reply=resolve)))
  const scanner = useScanner('api',''); await scanner.selectFile(file('first'))
  const pending = scanner.recognize(); await vi.waitFor(() => expect(reply).toBeTypeOf('function'))
  await scanner.selectFile(file('second'))
  reply(Response.json({status:'matched',slug:cards[0].slug})); await pending
  expect(scanner.phase.value).toBe('preview'); expect(scanner.file.value!.name).toBe('second.jpg'); expect(scanner.wine.value).toBeNull()
})
it('switching mode resets photo and revokes preview URL', async () => {
  const scanner = useScanner('demo',''); await scanner.selectFile(file()); scanner.changeMode('api')
  expect(scanner.file.value).toBeNull();expect(scanner.phase.value).toBe('start');expect(URL.revokeObjectURL).toHaveBeenCalled()
})
it('retries a connection failure using the same selected photo', async () => {
  const fetch = vi.fn().mockRejectedValueOnce(new Error('offline')).mockResolvedValueOnce(new Response(null,{status:204})).mockResolvedValueOnce(Response.json({status:'no_confident_match',slug:null,reason_code:'low_match_score'}))
  vi.stubGlobal('fetch',fetch)
  const scanner = useScanner('api','');await scanner.selectFile(file());await scanner.recognize()
  expect(scanner.phase.value).toBe('error');expect(scanner.file.value).not.toBeNull()
  await scanner.recognize();expect(scanner.phase.value).toBe('negative');expect(scanner.outcome.value?.slug).toBeNull()
})
it('keeps a matched wine when alternatives fail and supports retry', async () => {
  const fetch = vi.fn().mockResolvedValueOnce(new Response(null,{status:204})).mockResolvedValueOnce(Response.json({status:'matched',slug:cards[0].slug})).mockResolvedValueOnce(Response.json(cards[0])).mockResolvedValue(new Response(null,{status:503}))
  vi.stubGlobal('fetch',fetch)
  const scanner = useScanner('api',''); await scanner.selectFile(file());await scanner.recognize()
  await vi.waitFor(()=>expect(scanner.alternativesError.value).not.toBe(''))
  expect(scanner.phase.value).toBe('result');expect(scanner.wine.value?.slug).toBe(cards[0].slug)
})
it('times out slow readiness and lets the user retry', async () => {
  vi.useFakeTimers()
  vi.stubGlobal('fetch',vi.fn().mockImplementation((_url,options)=>new Promise((_resolve,reject)=>options.signal.addEventListener('abort',()=>reject(options.signal.reason)))))
  const scanner = useScanner('api','');await scanner.selectFile(file());const pending=scanner.recognize()
  await vi.advanceTimersByTimeAsync(20001);await pending
  expect(scanner.phase.value).toBe('error');expect(scanner.error.value).toContain('слишком долго');expect(scanner.file.value).not.toBeNull()
})
it('ignores a late wine card after a new photo, even if the transport ignores abort', async () => {
  let cardReply!: (response: Response) => void
  vi.stubGlobal('fetch',vi.fn().mockResolvedValueOnce(new Response(null,{status:204})).mockResolvedValueOnce(Response.json({status:'matched',slug:cards[0].slug})).mockImplementationOnce(()=>new Promise(resolve=>cardReply=resolve)))
  const scanner=useScanner('api','');await scanner.selectFile(file('old'));const pending=scanner.recognize()
  await vi.waitFor(()=>expect(cardReply).toBeTypeOf('function'));await scanner.selectFile(file('new'))
  cardReply(Response.json(cards[0]));await pending
  expect(scanner.phase.value).toBe('preview');expect(scanner.wine.value).toBeNull();expect(scanner.file.value?.name).toBe('new.jpg')
})
it('does not restore a delayed demo sample after switching to API',async()=>{
  let reply!: (response:Response)=>void
  vi.stubGlobal('fetch',vi.fn().mockImplementation(()=>new Promise(resolve=>reply=resolve)))
  const scanner=useScanner('demo','');const pending=scanner.loadSample('/demo/example.webp')
  scanner.changeMode('api');reply(new Response('image'));await pending
  expect(scanner.file.value).toBeNull();expect(scanner.phase.value).toBe('start');expect(scanner.checking.value).toBe(false)
})
