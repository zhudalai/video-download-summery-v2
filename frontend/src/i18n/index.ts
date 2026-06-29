import { createI18n } from 'vue-i18n'
import en from './locales/en/common.json'
import zhCN from './locales/zh-CN/common.json'
import ja from './locales/ja/common.json'

const i18n = createI18n({
  legacy: false,
  locale: 'en',
  fallbackLocale: 'en',
  messages: { en, 'zh-CN': zhCN, ja },
})

export default i18n
