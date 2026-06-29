import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useSummaryStore = defineStore('summary', () => {
  const content = ref('')
  const status = ref<'idle' | 'loading_subtitles' | 'generating' | 'done' | 'error'>('idle')
  const error = ref('')
  const videoInfo = ref<any>(null)

  const reset = () => {
    content.value = ''
    status.value = 'idle'
    error.value = ''
    videoInfo.value = null
  }

  // 供 SummaryTab 同步流式内容
  const appendContent = (chunk: string) => { content.value += chunk }
  const setStatus = (s: typeof status.value) => { status.value = s }
  const setError = (e: string) => { error.value = e }

  return { content, status, error, videoInfo, reset, appendContent, setStatus, setError }
})
