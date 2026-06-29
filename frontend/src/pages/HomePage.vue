<script setup lang="ts">
import { useI18n } from 'vue-i18n'
const { t } = useI18n()
</script>
<template>
  <div class="max-w-4xl mx-auto px-4 py-16 text-center">
    <h1 class="text-4xl font-bold mb-4">{{ t('common.appName') }}</h1>
    <p class="text-xl text-gray-600 mb-8">Paste any video link to download and get AI summary</p>
    <router-link to="/download" class="btn-primary text-lg px-8 py-3">{{ t('download.submit') }}</router-link>
  </div>
</template>
