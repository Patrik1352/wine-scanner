<script setup lang="ts">
import type { Wine } from '../services/types'
const props = defineProps<{ wine: Wine; demo: boolean }>()
const number = (value: number) => value.toLocaleString('ru-RU', { maximumFractionDigits: 2 })
const alcohol = computed(() => props.wine.alcohol_percent === null ? null : `${number(props.wine.alcohol_percent)}${props.wine.alcohol_max_percent !== null ? '–' + number(props.wine.alcohol_max_percent) : ''}%`)
const facts = computed(() => [
  ['Регион', props.wine.region], ['Сорта винограда', props.wine.grapes.join(', ') || null],
  ['Категория', props.wine.category], ['Сахаристость', props.wine.sweetness_from_category],
  ['Крепость', alcohol.value], ['Температура подачи', props.wine.serving_temperature_c ? props.wine.serving_temperature_c + ' °C' : null]
])
</script>
<template>
  <article class="wine-card">
    <div class="wine-portrait"><span class="portrait-tag">{{ wine.color_category || 'Вино из каталога' }}</span><WineImage :src="wine.image_url" :name="wine.name" /><span class="portrait-foot">РОССИЙСКОЕ ВИНО</span></div>
    <div class="wine-content">
      <p class="eyebrow success"><AppIcon name="check" />{{ demo ? 'Карточка демо-сценария' : 'Вино найдено' }}</p>
      <p v-if="wine.winery_name" class="winery">{{ wine.winery_name }}</p>
      <h2>{{ wine.name }}</h2>
      <div class="ratings">
        <div><span>Народный рейтинг</span><strong v-if="wine.public_rating !== null"><AppIcon name="star" />{{ number(wine.public_rating) }}</strong><small v-else>Пока нет оценок</small></div>
        <div><span>Оценка гида</span><strong v-if="wine.guide_rating !== null">{{ number(wine.guide_rating) }}</strong><small v-else>Не указана</small></div>
      </div>
      <dl class="facts"><div v-for="[label, value] in facts" :key="label!" :class="{ missing: !value }"><dt>{{ label }}</dt><dd>{{ value || 'Нет данных в каталоге' }}</dd></div></dl>
      <div v-if="wine.description" class="description"><h3>Характер вина</h3><p>{{ wine.description }}</p></div>
      <p v-else class="muted">Описание в каталоге пока не добавлено.</p>
      <a v-if="wine.source_url" class="source-link" :href="wine.source_url" target="_blank" rel="noopener noreferrer">Карточка на «Своё Вино» <span aria-hidden="true">↗</span></a>
    </div>
  </article>
</template>
