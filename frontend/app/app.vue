<script setup lang="ts">
import { nextTick, onBeforeUnmount, ref, watch } from 'vue'
import { useScanner } from './composables/useScanner'
import { CameraSession } from './services/camera'
import { ACCEPT, cameraError, reasonHints } from './services/photo'
import { alternativeReasons } from './services/api'
import type { DemoScenario, Mode } from './services/types'
const config = useRuntimeConfig()
const scanner = useScanner(config.public.recognitionMode === 'api' ? 'api' : 'demo', config.public.apiBase)
const { mode, scenario, phase, file, photo, checking, wine, outcome, error, alternatives, alternativesError, alternativesLoading } = scanner
const upload = ref<HTMLInputElement | null>(null)
const video = ref<HTMLVideoElement | null>(null)
const cameraDialog = ref<HTMLDialogElement | null>(null)
const heading = ref<HTMLElement | null>(null)
const cameraOpen = ref(false)
const cameraReady = ref(false)
const camera = new CameraSession()
let cameraGeneration = 0
const scenarios: [DemoScenario, string][] = [
  ['matched', 'Найдено · Фанагория'], ['ratings', 'Найдено · две оценки'], ['incomplete', 'Неполная карточка'],
  ['low_quality', 'Нужно переснять · размыто'], ['multiple_bottles', 'Несколько бутылок'], ['ambiguous_pair', 'Похожие этикетки'],
  ['no_confident_match', 'Нет надёжного совпадения'], ['offline', 'Ошибка соединения'], ['unavailable', 'Сервис недоступен']
]
const heroBottle = '/demo/fanagoriya-cru-lermont-chardonnay-shardone-beloe-suhoe-14.webp'
watch(phase, async value => { if (['result', 'negative', 'error', 'preview'].includes(value)) { await nextTick(); heading.value?.focus({ preventScroll: true }) } })
async function selected(event: Event) {
  const input = event.target as HTMLInputElement
  const next = input.files?.[0]; input.value = ''
  if (next) await scanner.selectFile(next)
}
function closeCamera() {
  cameraGeneration++
  camera.close()
  cameraReady.value = false; cameraOpen.value = false
  cameraDialog.value?.close()
}
async function openCamera() {
  scanner.stopRequest()
  if (!navigator.mediaDevices?.getUserMedia) { scanner.reportError('Камера доступна по HTTPS или на localhost. Выберите готовое фото.'); return }
  cameraOpen.value = true
  await nextTick(); cameraDialog.value?.showModal()
  const id = ++cameraGeneration
  try {
    if (video.value) {
      const ready = await camera.open(video.value)
      if (id === cameraGeneration) cameraReady.value = ready
    }
  } catch (e) { if (id === cameraGeneration) { closeCamera(); scanner.reportError(cameraError(e)) } }
}
async function capture() {
  const target = video.value
  if (!target?.videoWidth) return
  try {
    const image = await camera.capture(target)
    if (!image) return
    closeCamera()
    await scanner.selectFile(image)
  } catch (e) { closeCamera(); scanner.reportError(e instanceof Error ? e.message : 'Не удалось сохранить кадр.') }
}
async function sample() { await scanner.loadSample(heroBottle) }

function setMode(event: Event) { closeCamera(); scanner.changeMode((event.target as HTMLSelectElement).value as Mode) }
function setScenario(event: Event) { scanner.changeScenario((event.target as HTMLSelectElement).value as DemoScenario) }
onBeforeUnmount(() => { closeCamera(); scanner.reset() })
</script>

<template>
  <a class="skip-link" href="#main">Перейти к сканеру</a>
  <header class="site-header">
    <button class="brand" aria-label="Своё вино — на главный экран" @click="scanner.reset"><span class="brand-symbol"><AppIcon name="glass" /></span><span>своё<span class="brand-wine">вино</span></span></button>
    <nav aria-label="Основная навигация"><a href="#main" class="nav-active">Сканер вина</a><a v-if="phase === 'start'" class="how-link" href="#how">Как это работает</a></nav>
    <span class="header-note">Открывайте российское <span>18+</span></span>
  </header>
  <div class="mode-bar" :class="{ live: mode === 'api' }">
    <div class="mode-explanation"><span class="status-dot" /><strong>{{ mode === 'demo' ? 'Демонстрационный режим' : 'Режим реального API' }}</strong><span>{{ mode === 'demo' ? 'Ответ задан сценарием, фото не распознаётся' : 'Фото отправляется в подключённый сервис' }}</span></div>
    <details class="demo-settings"><summary>Настройки {{ mode === 'demo' ? 'демо' : 'API' }}</summary><div class="settings-panel">
      <label for="mode">Режим работы</label><select id="mode" :value="mode" @change="setMode"><option value="demo">Демонстрация</option><option value="api">Реальный API</option></select>
      <template v-if="mode === 'demo'"><label for="scenario">Фиксированный сценарий</label><select id="scenario" :value="scenario" @change="setScenario"><option v-for="[value, label] in scenarios" :key="value" :value="value">{{ label }}</option></select><p>Любая фотография даёт выбранный ответ. Распознающая модель не используется.</p></template>
      <p v-else>Сервис: {{ config.public.apiBase || 'тот же адрес, что у приложения' }}. Адрес задаётся при запуске.</p>
    </div></details>
  </div>
  <main id="main">
    <template v-if="phase === 'start'">
      <section class="hero">
        <div class="hero-copy"><p class="eyebrow"><span class="tiny-line" /> СКАНЕР РОССИЙСКИХ ВИН</p><h1>У каждой бутылки<br>своя <em>история.</em></h1><p class="hero-lead">Начните с этикетки. Узнайте больше о вине,<br class="desktop-break"> найдите гастросочетания и откройте похожее.</p>
          <div class="start-actions"><button class="button primary" @click="openCamera"><AppIcon name="camera" />Сфотографировать</button><button class="button secondary" @click="upload?.click()"><AppIcon name="image" />Выбрать фото</button></div>
          <p class="file-note">JPEG, PNG, WebP или HEIC · до 15 МБ</p>
          <button v-if="mode === 'demo'" class="text-button sample" @click="sample">Попробовать на примере <AppIcon name="arrow" /></button>
        </div>
        <div class="hero-art" aria-label="Бутылка Cru Lermont Chardonnay из демонстрационного каталога">
          <span class="art-caption">БЛИЖЕ К СВОЕМУ</span><div class="art-orbit orbit-one" /><div class="art-orbit orbit-two" /><div class="bottle-shadow" />
          <img class="hero-bottle" :src="heroBottle" alt="Cru Lermont Chardonnay, Фанагория">
          <div class="scan-frame"><i /><i /><i /><i /><span class="scan-line" /></div>
          <div class="art-chip"><span class="chip-icon"><AppIcon name="scan" /></span><span>Всего одна фотография<small>Наведите камеру на этикетку</small></span></div>
          <span class="art-bottom">ЭТИКЕТКА → ЗНАКОМСТВО → ВПЕЧАТЛЕНИЕ</span>
        </div>
      </section>
    </template>
    <section v-else class="workspace" :aria-busy="phase === 'processing' || checking">
      <div class="workspace-heading"><div><p class="eyebrow">СКАНЕР РОССИЙСКИХ ВИН</p><h1 ref="heading" tabindex="-1">{{ phase === 'result' ? 'Знакомьтесь, ваше вино' : phase === 'processing' ? 'Знакомимся с этикеткой' : phase === 'preview' ? 'Всё готово к знакомству?' : phase === 'negative' ? (outcome?.status === 'needs_better_photo' ? 'Нужен ещё один кадр' : 'Пока без точного ответа') : 'Не получилось продолжить' }}</h1></div><button class="text-button" @click="scanner.reset"><AppIcon name="retry" />Новое сканирование</button></div>
      <template v-if="phase === 'result' && wine">
        <p v-if="mode === 'demo'" class="demo-result">Это демонстрационная карточка выбранного сценария. Содержимое фотографии не анализировалось.</p>
        <p v-if="mode === 'api' && outcome?.status === 'matched' && outcome.low_confidence" class="demo-result" role="status">Найдено наиболее похожее вино, но совпадение нужно проверить. Сравните название и этикетку на карточке с вашей бутылкой.</p>
        <WineCard :wine="wine" :demo="mode === 'demo'" />
        <section class="pairing-section"><div><p class="eyebrow">ВИНО ЗА ВАШИМ СТОЛОМ</p><h2>К чему подать</h2><p>Гастросочетания из карточки вина.</p></div><div v-if="wine.food_pairings.length" class="pairing-tags"><span v-for="food in wine.food_pairings" :key="food"><AppIcon name="leaf" />{{ food }}</span></div><p v-else class="muted">Гастросочетания для этого вина в каталоге не указаны.</p></section>
        <section class="alternatives-section"><div class="section-title"><div><p class="eyebrow">ПРОДОЛЖИТЬ ЗНАКОМСТВО</p><h2>Чем заменить</h2></div><span class="small-pill">Отдельная подборка</span></div><p class="section-intro">Похожие вина по сведениям каталога. Это альтернативы, а не другие результаты распознавания.</p>
          <p v-if="alternativesLoading" role="status">Подбираем похожие вина…</p>
          <div v-else-if="alternativesError" role="status"><p>{{ alternativesError }}</p><button class="text-button" @click="scanner.loadAlternatives">Повторить загрузку</button></div>
          <div v-else-if="alternatives.length" class="alternatives-grid"><article v-for="item in alternatives" :key="item.slug" class="alternative-card"><div class="alternative-image"><WineImage :src="item.image_url" :name="item.name" /></div><div><p class="muted">{{ item.winery_name }}</p><h3>{{ item.name }}</h3><p v-for="reason in alternativeReasons(wine, item).slice(0, 2)" :key="reason" class="alternative-reason">{{ reason }}</p><a v-if="item.source_url" :href="item.source_url" target="_blank" rel="noopener noreferrer" class="source-link">Подробнее о вине ↗</a></div></article></div>
          <p v-else class="muted">В доступном наборе нет альтернатив с подтверждёнными общими признаками.</p>
        </section>
        <div class="result-bottom"><button class="button primary" @click="scanner.reset"><AppIcon name="scan" />Сканировать другое вино</button><small>{{ mode === 'demo' ? 'Сведения из конкурсного каталога · сентябрь 2026' : 'Сведения из подключённого каталога' }}</small></div>
      </template>
      <div v-else class="scan-workspace">
        <div class="photo-panel"><img v-if="photo" :src="photo" alt="Выбранная фотография для распознавания" /><div v-else class="photo-empty"><AppIcon name="image" /><span>Выберите фотографию</span></div><span v-if="photo" class="photo-label">Ваша фотография</span><div v-if="phase === 'processing'" class="processing-sweep" /></div>
        <div class="scan-instructions">
          <template v-if="phase === 'preview'"><span class="step-number">01 / ФОТОГРАФИЯ</span><h2>Этикетка хорошо видна?</h2><p>В кадре должна быть одна бутылка. Название, винодельня и мелкий текст помогут найти точную карточку.</p><p v-if="mode === 'demo'" class="inline-note">Демо: {{ scenarios.find(s => s[0] === scenario)?.[1] }}. Ответ не зависит от фото.</p><button class="button primary" :disabled="checking" @click="scanner.recognize"><AppIcon name="scan" />{{ mode === 'demo' ? 'Показать демо-результат' : 'Распознать вино' }}<AppIcon name="arrow" /></button></template>
          <template v-else-if="phase === 'processing'"><span class="loader" /><h2>{{ mode === 'demo' ? 'Показываем, как это работает' : 'Ищем вино в каталоге' }}</h2><p role="status">{{ mode === 'demo' ? 'Сейчас откроется результат выбранного демо-сценария.' : 'Изучаем этикетку на вашей фотографии. Это займёт немного времени.' }}</p><button class="button secondary" @click="scanner.stopRequest">Отменить обработку</button></template>
          <template v-else-if="phase === 'negative'"><span class="message-symbol"><AppIcon name="scan" /></span><h2>{{ outcome?.status === 'needs_better_photo' ? 'Помогите увидеть детали' : 'Совпадение не подтверждено' }}</h2><p role="status">{{ outcome && outcome.status !== 'matched' ? reasonHints[outcome.reason_code] || 'Не хватает читаемых деталей. Снимите этикетку крупнее, без бликов, или покажите контрэтикетку.' : '' }}</p><p v-if="outcome?.status === 'no_confident_match'" class="muted">Это не означает, что вина нет в каталоге.</p><button class="button primary" @click="openCamera"><AppIcon name="camera" />Переснять этикетку</button></template>
          <template v-else><span class="message-symbol"><AppIcon name="info" /></span><h2>Попробуем ещё раз</h2><p role="alert">{{ error }}</p><button v-if="file" class="button primary" @click="scanner.recognize"><AppIcon name="retry" />Отправить фото повторно</button><button v-else class="button primary" @click="upload?.click()"><AppIcon name="image" />Выбрать фото</button></template>
          <button v-if="phase !== 'processing' && (file || phase === 'negative')" class="text-button replace" @click="upload?.click()"><AppIcon name="image" />Заменить фотографию</button>
          <p class="privacy-note"><AppIcon name="shield" />{{ mode === 'demo' ? 'В демо фотография остаётся в вашем браузере.' : 'Фото отправится только в настроенный сервис распознавания.' }}</p>
        </div>
      </div>
    </section>
    <p v-if="checking" class="checking" role="status">Проверяем фотографию…</p>
    <section v-if="phase === 'start'" id="how" class="how-section"><div class="section-title"><h2>От этикетки — к открытию</h2><span class="muted">Три простых шага</span></div><div class="steps"><article><span>01</span><div><h3>Поймайте этикетку</h3><p>Одна бутылка, хороший свет и никаких бликов.</p></div><AppIcon name="camera" /></article><article><span>02</span><div><h3>Узнайте своё вино</h3><p>Винодельня, сорта и всё, что делает его особенным.</p></div><AppIcon name="glass" /></article><article><span>03</span><div><h3>Найдите сочетание</h3><p>К чему подать сегодня и что попробовать потом.</p></div><AppIcon name="leaf" /></article></div></section>
    <input ref="upload" class="sr-only" tabindex="-1" type="file" :accept="ACCEPT" aria-label="Выбрать фотографию вина" @change="selected">
    <dialog ref="cameraDialog" class="camera-dialog" aria-labelledby="camera-title" @cancel.prevent="closeCamera">
      <div v-if="cameraOpen" class="camera-content"><div class="camera-top"><h2 id="camera-title">Поместите этикетку в кадр</h2><button class="icon-button" aria-label="Закрыть камеру" @click="closeCamera"><AppIcon name="close" /></button></div><video ref="video" autoplay muted playsinline aria-label="Изображение с камеры" /><p role="status">{{ cameraReady ? 'Одна бутылка, без бликов. Коснитесь кнопки, чтобы сделать снимок.' : 'Ожидаем доступ к камере…' }}</p><button class="button primary" :disabled="!cameraReady" @click="capture"><AppIcon name="camera" />Сделать снимок</button></div>
    </dialog>
  </main>
  <footer><span class="footer-brand">своё вино <span>/ сканер</span></span><p>Чрезмерное употребление алкоголя вредит вашему здоровью</p><span class="age">18+</span></footer>
</template>
