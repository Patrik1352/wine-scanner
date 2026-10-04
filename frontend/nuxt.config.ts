const apiInternalUrl = process.env.NUXT_API_INTERNAL_URL || 'http://127.0.0.1:8080'

export default defineNuxtConfig({
  compatibilityDate: '2026-09-16',
  devtools: { enabled: false },
  css: ['~/assets/css/main.css'],
  runtimeConfig: { public: { apiBase: '', recognitionMode: 'demo' } },
  routeRules: {
    '/v1/**': { proxy: apiInternalUrl + '/v1/**' },
    '/health/**': { proxy: apiInternalUrl + '/health/**' },
  },
  app: { head: { htmlAttrs: { lang: 'ru' }, title: 'Сканер российских вин — Своё вино', meta: [{ name: 'description', content: 'Узнайте вино по этикетке, найдите гастросочетания и похожие вина.' }, { name: 'theme-color', content: '#7a303b' }] } }
})
