<script setup lang="ts">
import { ref, computed } from 'vue'
import { useVideoStore } from '@/stores/video'
import VideoInfoPanel from '@/components/VideoInfoPanel.vue'
import VideoSummary from '@/components/VideoSummary.vue'
import LanguageSwitcher from '@/components/LanguageSwitcher.vue'
import { useI18n } from 'vue-i18n'

const { t } = useI18n()
const videoStore = useVideoStore()

const url = ref('')
const isParsing = ref(false)
const parseError = ref('')

const hasVideo = computed(() => !!videoStore.videoInfo)

const handleSubmit = async () => {
  if (!url.value.trim()) return
  isParsing.value = true
  parseError.value = ''
  videoStore.videoInfo = null
  videoStore.url = url.value
  try {
    const resp = await fetch(`${import.meta.env.VITE_API_URL || ''}/api/videos/parse`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url: url.value }),
    })
    const data = await resp.json()
    if (!resp.ok) {
      parseError.value = data.detail || '解析失败'
      return
    }
    videoStore.videoInfo = data
    videoStore.status = 'ready'
  } catch (e: any) {
    parseError.value = e.message || '网络错误'
  } finally {
    isParsing.value = false
  }
}

const handleDownload = async (formatId: string) => {
  const form = document.createElement('form')
  form.method = 'POST'
  form.action = '/api/videos/download'
  for (const [name, value] of Object.entries({ url: videoStore.url, format_id: formatId })) {
    const input = document.createElement('input')
    input.name = name; input.value = value as string
    form.appendChild(input)
  }
  document.body.appendChild(form)
  form.submit()
  document.body.removeChild(form)
}
</script>

<template>
  <div class="min-h-screen bg-gray-50">
    <!-- 顶部栏 -->
    <header class="bg-white shadow-sm border-b border-gray-200">
      <div class="max-w-7xl mx-auto px-4 h-16 flex items-center justify-between">
        <h1 class="text-xl font-bold text-primary">AI Video Summary</h1>
        <div class="flex items-center gap-4">
          <LanguageSwitcher />
        </div>
      </div>
    </header>

    <main class="max-w-7xl mx-auto px-4 py-6">
      <!-- 顶部输入区 -->
      <div class="max-w-3xl mx-auto mb-8">
        <div class="flex gap-3">
          <input
            v-model="url"
            type="text"
            :placeholder="t('workspace.inputPlaceholder')"
            class="flex-1 border border-gray-300 rounded-lg px-4 py-3 focus:outline-none focus:ring-2 focus:ring-primary focus:border-primary"
            @keydown.enter="handleSubmit"
          />
          <button
            type="submit"
            :disabled="isParsing"
            class="btn-primary px-8 py-3 font-medium"
            @click="handleSubmit"
          >
            {{ isParsing ? t('workspace.parsing') : t('workspace.analyzeBtn') }}
          </button>
        </div>
        <p v-if="parseError" class="mt-3 text-sm text-red-600 bg-red-50 px-4 py-2 rounded-lg">
          {{ parseError }}
        </p>
      </div>

      <!-- 空状态 -->
      <div v-if="!hasVideo" class="max-w-xl mx-auto text-center py-16">
        <div class="text-6xl mb-4">🎬</div>
        <h2 class="text-xl font-semibold text-gray-700 mb-2">{{ t('workspace.emptyTitle') }}</h2>
        <p class="text-gray-500">{{ t('workspace.emptyDesc') }}</p>
      </div>

      <!-- 双栏工作台 -->
      <div v-else class="grid grid-cols-1 lg:grid-cols-[1fr_1.5fr] gap-6">
        <aside class="lg:sticky lg:top-20 self-start space-y-6">
          <VideoInfoPanel :videoInfo="videoStore.videoInfo!" @download="handleDownload" />
        </aside>

        <main class="min-w-0">
          <VideoSummary
            :key="videoStore.url"
            :video-url="videoStore.url"
            :video-title="videoStore.videoInfo?.title || ''"
          />
        </main>
      </div>
    </main>
  </div>
</template>
