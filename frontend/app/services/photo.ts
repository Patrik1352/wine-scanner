import { ServiceError } from './api'
const HEIC_TYPES = new Set(['image/heic', 'image/heif'])
const HEIC_EXTENSION = /\.(heic|heif)$/i

export function isHeic(file: File) {
  return HEIC_TYPES.has(file.type.toLowerCase()) || HEIC_EXTENSION.test(file.name)
}

async function hasHeicSignature(file: File) {
  const bytes = new Uint8Array(await file.slice(0, 32).arrayBuffer())
  const text = (from: number, to: number) => String.fromCharCode(...bytes.slice(from, to))
  if (text(4, 8) !== 'ftyp') return false
  const brands = ['heic', 'heif', 'heix', 'heis', 'hevc', 'hevx', 'mif1', 'msf1']
  return brands.some(brand => text(8, 12) === brand || text(16, 20) === brand || text(20, 24) === brand || text(24, 28) === brand)
}

async function convertToJpeg(file: File): Promise<File> {
  try {
    const { default: heic2any } = await import('heic2any')
    const converted = await heic2any({ blob: file, toType: 'image/jpeg', quality: .9 })
    const blob = Array.isArray(converted) ? converted[0] : converted
    if (!blob) throw new Error('Конвертер не вернул изображение')
    const name = /\.[^.]+$/.test(file.name) ? file.name.replace(/\.[^.]+$/, '.jpg') : `${file.name || 'photo'}.jpg`
    return new File([blob], name, { type: 'image/jpeg', lastModified: file.lastModified })
  } catch {
    throw new ServiceError('format', 'Не удалось преобразовать HEIC. Откройте фото в приложении «Фото», сохраните как JPEG и попробуйте снова.')
  }
}

export async function preparePhoto(file: File): Promise<File> {
  if (!isHeic(file) && !await hasHeicSignature(file)) return file
  return convertToJpeg(file)
}

export async function forceJpegConversion(file: File): Promise<File> {
  return convertToJpeg(file)
}

export const ACCEPT = 'image/jpeg,image/png,image/webp,image/heic,image/heif,.heic,.heif'
export function validateFile(file: File) {
  if (!['image/jpeg', 'image/png', 'image/webp'].includes(file.type)) throw new ServiceError('format', 'Этот формат не поддерживается. Выберите JPEG, PNG, WebP или HEIC.')
  if (file.size > 15 * 1024 * 1024) throw new ServiceError('size', 'Фотография слишком большая. Выберите файл до 15 МБ.')
  if (file.size === 0) throw new ServiceError('format', 'Файл пустой. Выберите другую фотографию.')
}
export async function validatePhoto(file: File, url: string) {
  validateFile(file)
  await new Promise<void>((resolve, reject) => {
    const img = new Image()
    img.onload = () => {
      if (img.naturalWidth * img.naturalHeight > 30_000_000) reject(new ServiceError('size', 'Слишком высокое разрешение. Уменьшите фотографию до 30 мегапикселей.'))
      else resolve()
    }
    img.onerror = () => reject(new ServiceError('format', 'Не удалось открыть изображение. Возможно, файл повреждён. Выберите другое фото.'))
    img.src = url
  })
}
export const reasonHints: Record<string, string> = {
  multiple_bottles: 'В кадре несколько бутылок. Приблизьте одну так, чтобы её этикетка занимала большую часть снимка.',
  low_quality: 'Этикетка плохо читается. Протрите объектив, добавьте света и держите телефон неподвижно.',
  blurry: 'Фото размыто. Коснитесь этикетки на экране для фокусировки и сделайте новый снимок.',
  glare: 'Блик закрывает этикетку. Отключите вспышку и немного измените угол съёмки.',
  too_dark: 'На фото темно. Переместите бутылку ближе к свету и снимите без вспышки.',
  ambiguous_pair: 'У нескольких вин похожие этикетки. Снимите крупно год урожая или контрэтикетку.',
  low_match_score: 'По этому снимку не удалось подтвердить точное вино. Попробуйте снять этикетку ближе или сфотографировать её с другой стороны.'
}
export function cameraError(error: unknown): string {
  const name = error instanceof Error || error instanceof DOMException ? error.name : ''
  if (['NotAllowedError', 'SecurityError'].includes(name)) return 'Нет доступа к камере. Разрешите его в настройках браузера или выберите готовое фото.'
  if (name === 'NotFoundError') return 'Камера не найдена. Выберите фотографию из галереи.'
  return 'Не удалось открыть камеру. Возможно, она занята другим приложением. Выберите готовое фото или попробуйте ещё раз.'
}
