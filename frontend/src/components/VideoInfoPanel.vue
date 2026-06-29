<script setup lang="ts">
import { ref, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import type { VideoInfo } from '@/stores/video'

const { t } = useI18n()

const props = defineProps<{ videoInfo: VideoInfo }>()

const emit = defineEmits<{
  (e: 'download', formatId: string): void
}>()

function parseHeight(resolution: string): number {
  const m = resolution?.match(/(\d+)x(\d+)/)
  return m ? parseInt(m[2], 10) : 0
}

// 视频格式(有画面)
const videoFormats = computed(() => {
  const all = (props.videoInfo.formats || []).filter((f) => {
    const hasVideo = f.vcodec && f.vcodec !== 'none'
    const looksLikeAudio = /audio/i.test(f.resolution || '')
    return hasVideo && !looksLikeAudio
  })
  // 只显示 >=720P;没有则 fallback 到最清晰的 1 个
  const high = all.filter((f) => parseHeight(f.resolution) >= 720)
  return high.length > 0 ? high : all.slice(0, 1)
})

// 音频格式(仅音频)
const audioFormats = computed(() => {
  return (props.videoInfo.formats || []).filter((f) => {
    return f.acodec && f.acodec !== 'none' && (!f.vcodec || f.vcodec === 'none')
  })
})

// 构造画质选项:1080P → 720P → 仅音频(fallback)
const selectedFormatId = ref<string>('best')

const qualityOptions = computed(() => {
  const opts: Array<{ format_id: string; label: string; is_audio?: boolean }> = []
  // 1080P
  const f1080 = videoFormats.value.find(f => parseHeight(f.resolution) >= 1080)
  if (f1080) opts.push({ format_id: f1080.format_id, label: t('format.1080p') })
  // 720P
  const f720 = videoFormats.value.find(f => parseHeight(f.resolution) >= 720)
  if (f720) opts.push({ format_id: f720.format_id, label: t('format.720p') })
  // 仅音频(最佳音频)
  const bestAudio = audioFormats.value[0]
  if (bestAudio) opts.push({ format_id: bestAudio.format_id, label: t('format.audio_only'), is_audio: true })
  // 都没有, fallback 到 best
  if (opts.length === 0) opts.push({ format_id: 'best', label: t('format.best') })
  return opts
})

function formatDuration(seconds: number): string {
  const m = Math.floor(seconds / 60)
  const s = Math.floor(seconds % 60)
  return `${m}:${String(s).padStart(2, '0')}`
}

function onDownload() {
  if (selectedFormatId.value) {
    emit('download', selectedFormatId.value)
  }
}
</script>

<template>
  <div>
    <img
      v-if="videoInfo.thumbnail"
      :src="videoInfo.thumbnail"
      :alt="videoInfo.title"
      class="w-full aspect-video object-cover rounded-lg bg-gray-100 mb-4"
    />
    <div
      v-else
      class="w-full aspect-video rounded-lg bg-gray-100 mb-4 flex items-center justify-center text-gray-400"
    >
      {{ t('common.noThumbnail') }}
    </div>

    <h2 class="text-xl font-semibold text-gray-900 mb-2">
      {{ videoInfo.title }}
    </h2>

    <div class="flex flex-wrap gap-x-4 gap-y-1 text-sm text-gray-500 mb-4">
      <span v-if="videoInfo.channel">{{ videoInfo.channel }}</span>
      <span v-if="videoInfo.duration">{{ formatDuration(videoInfo.duration) }}</span>
      <span v-if="videoInfo.platform">{{ videoInfo.platform }}</span>
      <span v-if="videoFormats.length">{{ videoFormats.length }} {{ t('video.formats') }}</span>
    </div>

    <div class="mb-4">
      <label class="block text-sm font-medium text-gray-700 mb-2">
        {{ t('video.quality') }}
      </label>
      <div class="space-y-2">
        <button
          v-for="opt in qualityOptions"
          :key="opt.format_id"
          type="button"
          class="w-full text-left px-3 py-2 border rounded-lg text-sm transition-colors"
          :class="
            selectedFormatId === opt.format_id
              ? 'border-primary bg-primary/5 text-primary'
              : 'border-gray-200 text-gray-700 hover:border-gray-300'
          "
          @click="selectedFormatId = opt.format_id"
        >
          <span class="font-medium">{{ opt.label }}</span>
          <span v-if="!opt.is_audio" class="ml-2 text-xs text-amber-600">{{ t('format.need_merge') }}</span>
        </button>
      </div>
    </div>

    <button
      class="btn-primary w-full py-3 mt-4 font-medium"
      :disabled="!selectedFormatId"
      @click="onDownload"
    >
      {{ t('video.downloadNow') }}
    </button>
  </div>
</template>
