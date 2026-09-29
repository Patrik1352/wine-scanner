import { ref, shallowRef } from 'vue'
import { createService, ServiceError } from '../services/api'
import { forceJpegConversion, preparePhoto, validatePhoto } from '../services/photo'
import type { Wine, Mode, DemoScenario, Recognition } from '../services/types'

export function useScanner(initialMode: Mode, apiBase: string) {
  const mode = ref<Mode>(initialMode)
  const scenario = ref<DemoScenario>('matched')
  const phase = ref<'start' | 'preview' | 'processing' | 'result' | 'negative' | 'error'>('start')
  const file = shallowRef<File | null>(null)
  const photo = ref('')
  const checking = ref(false)
  const wine = ref<Wine | null>(null)
  const outcome = ref<Recognition | null>(null)
  const error = ref('')
  const alternatives = ref<Wine[]>([])
  const alternativesError = ref('')
  const alternativesLoading = ref(false)
  let generation = 0
  let controller: AbortController | undefined
  function cancel() { generation++; controller?.abort(); controller = undefined; checking.value = false; alternativesLoading.value = false }
  function clearResult() { wine.value = null; outcome.value = null; alternatives.value = []; alternativesError.value = ''; error.value = '' }
  function reset() {
    cancel(); clearResult()
    if (photo.value) URL.revokeObjectURL(photo.value)
    photo.value = ''; file.value = null; phase.value = 'start'
  }
  function changeMode(value: Mode) { reset(); mode.value = value }
  function changeScenario(value: DemoScenario) {
    cancel(); clearResult(); scenario.value = value; phase.value = file.value ? 'preview' : 'start'
  }
  async function selectFile(next: File) {
    cancel(); clearResult(); checking.value = true
    const id = generation
    let url = ''
    try {
      const prepared = await preparePhoto(next)
      if (id !== generation) return
      url = URL.createObjectURL(prepared)
      await validatePhoto(prepared, url)
      if (id !== generation) { URL.revokeObjectURL(url); return }
      if (photo.value) URL.revokeObjectURL(photo.value)
      file.value = prepared; photo.value = url; phase.value = 'preview'
    } catch (e) {
      if (url) URL.revokeObjectURL(url)
      if (id !== generation) return
      error.value = e instanceof Error ? e.message : 'Не удалось открыть фото.'
      phase.value = 'error'
    } finally { if (id === generation) checking.value = false }
  }
  async function loadSample(url: string) {
    cancel(); clearResult(); checking.value = true
    const id = generation
    const active = new AbortController(); controller = active
    try {
      const response = await fetch(url, { signal: active.signal })
      if (!response.ok) throw new Error('Не удалось открыть пример. Выберите фото с устройства.')
      const blob = await response.blob()
      if (id === generation) await selectFile(new File([blob], 'demo-photo.webp', { type: 'image/webp' }))
    } catch (e) {
      if (id === generation) reportError(e instanceof Error ? e.message : 'Не удалось открыть пример.')
    } finally { if (id === generation) checking.value = false }
  }
  async function loadAlternatives() {
    if (!wine.value) return
    const id = generation
    const active = controller ?? new AbortController()
    controller = active
    const service = createService(mode.value, apiBase, scenario.value)
    alternativesLoading.value = true; alternativesError.value = ''
    const timer = setTimeout(() => active.abort(new ServiceError('timeout', 'Загрузка похожих вин заняла слишком много времени.')), 15000)
    try {
      const values = await service.alternatives(wine.value, active.signal)
      if (id === generation) alternatives.value = values
    } catch {
      if (id === generation) alternativesError.value = 'Не удалось загрузить альтернативы. Найденная карточка сохранена.'
    } finally { clearTimeout(timer); if (id === generation) { alternativesLoading.value = false; controller = undefined } }
  }
  async function recognize() {
    if (!file.value || checking.value) return
    cancel(); clearResult(); phase.value = 'processing'
    const id = generation
    const active = new AbortController(); controller = active
    const service = createService(mode.value, apiBase, scenario.value)
    const timer = setTimeout(() => active.abort(new ServiceError('timeout', 'Сервис отвечает слишком долго. Попробуйте ещё раз.')), 20000)
    try {
      await service.ready(active.signal)
      let result: Recognition
      try {
        result = await service.recognize(file.value, active.signal)
      } catch (firstError) {
        if (!(firstError instanceof ServiceError) || firstError.code !== 'format') throw firstError
        const converted = await forceJpegConversion(file.value)
        if (id !== generation) return
        const nextUrl = URL.createObjectURL(converted)
        try { await validatePhoto(converted, nextUrl) }
        catch (conversionError) { URL.revokeObjectURL(nextUrl); throw conversionError }
        if (photo.value) URL.revokeObjectURL(photo.value)
        file.value = converted; photo.value = nextUrl
        result = await service.recognize(converted, active.signal)
      }
      if (id !== generation) return
      outcome.value = result
      if (result.status === 'matched') {
        const card = await service.wine(result.slug, active.signal)
        if (id !== generation) return
        wine.value = card; phase.value = 'result'
      } else phase.value = 'negative'
    } catch (e) {
      if (id !== generation) return
      error.value = active.signal.aborted && active.signal.reason instanceof ServiceError ? active.signal.reason.message : e instanceof Error ? e.message : 'Произошла ошибка. Попробуйте ещё раз.'
      phase.value = 'error'
    } finally { clearTimeout(timer); if (id === generation) controller = undefined }
    if (id === generation && wine.value) void loadAlternatives()
  }
  function reportError(message: string) { cancel(); clearResult(); error.value = message; phase.value = 'error' }
  function stopRequest() { cancel(); phase.value = file.value ? 'preview' : 'start' }
  return { mode, scenario, phase, file, photo, checking, wine, outcome, error, alternatives, alternativesError, alternativesLoading, reset, changeMode, changeScenario, selectFile, loadSample, recognize, reportError, stopRequest, loadAlternatives }
}
