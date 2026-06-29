import { defineStore } from 'pinia'
import { ref } from 'vue'

export interface VideoFormat {
  format_id: string
  ext: string
  resolution: string
  filesize?: number
  vcodec?: string
  acodec?: string
  has_audio?: boolean  // true=音视频已合并,false=仅视频(需 ffmpeg 合并)
}

export interface VideoInfo {
  title: string
  duration: number
  platform: string
  thumbnail?: string
  channel?: string
  formats?: VideoFormat[]
  subtitle_languages?: string[]
  has_automatic_captions?: boolean
}

export const useVideoStore = defineStore('video', () => {
  const url = ref('')
  const status = ref<'idle' | 'parsing' | 'ready' | 'error'>('idle')
  const videoInfo = ref<VideoInfo | null>(null)
  const error = ref('')

  return { url, status, videoInfo, error }
})
