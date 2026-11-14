import 'vazirmatn/Vazirmatn-font-face.css'
import 'bootstrap-icons/font/bootstrap-icons.css'
import './styles/main.scss'

import { createPinia } from 'pinia'
import { createApp } from 'vue'

import App from './App.vue'
import { initTheme } from './composables/useTheme'
import { applyLocale, i18n } from './i18n'
import { router } from './router'

initTheme()
applyLocale(i18n.global.locale.value)

createApp(App).use(createPinia()).use(i18n).use(router).mount('#app')
