<script setup lang="ts">
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'

const { locale, availableLocales } = useI18n()
const open = ref(false)

const langLabels: Record<string, string> = {
  en: 'English',
  'zh-CN': '中文',
  ja: '日本語',
}

function switchLanguage(lang: string) {
  locale.value = lang
  document.documentElement.lang = lang
  localStorage.setItem('locale', lang)
  open.value = false
}
</script>

<template>
  <div class="relative">
    <button
      @click="open = !open"
      class="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-gray-300 bg-white hover:border-primary hover:text-primary transition-colors text-sm font-medium shadow-sm"
    >
      <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 5h12M9 3v2m1.048 9.5A18.022 18.022 0 016.412 9m6.088 9h7M11 21l5-10 5 10M12.751 5C11.783 10.77 8.07 15.61 3 18.129" />
      </svg>
      <span>{{ langLabels[locale] || locale }}</span>
      <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" />
      </svg>
    </button>
    <div
      v-if="open"
      class="absolute right-0 top-full mt-1 bg-white border border-gray-200 rounded-lg shadow-lg py-1 z-50 min-w-[120px]"
    >
      <button
        v-for="lang in availableLocales"
        :key="lang"
        @click="switchLanguage(lang)"
        :class="[
          'w-full text-left px-4 py-2 text-sm hover:bg-primary/10 transition-colors',
          locale === lang ? 'text-primary font-medium bg-primary/5' : 'text-gray-700'
        ]"
      >
        {{ langLabels[lang] || lang }}
      </button>
    </div>
  </div>
</template>
