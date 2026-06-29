<template>
  <div class="bg-white rounded-2xl border border-gray-200 shadow-lg overflow-hidden h-full flex flex-col">
    <!-- Tab 导航 -->
    <div class="flex border-b border-gray-200">
      <button
        v-for="tab in tabs"
        :key="tab.key"
        @click="activeTab = tab.key"
        :class="[
          'relative flex items-center gap-2 px-5 py-3.5 text-sm font-medium transition-all',
          activeTab === tab.key ? 'text-primary' : 'text-gray-500 hover:text-gray-700'
        ]"
      >
        <span>{{ tab.icon }}</span>
        <span>{{ tab.label }}</span>
        <div v-if="activeTab === tab.key" class="absolute bottom-0 left-0 right-0 h-0.5 bg-primary"></div>
      </button>
    </div>

    <!-- 内容区 -->
    <div class="p-5 sm:p-6 min-h-[400px] flex-1 overflow-y-auto">
      <!-- 总结摘要 Tab -->
      <div v-show="activeTab === 'summary'">
        <div v-if="loading && !summaryText" class="flex flex-col items-center justify-center py-16">
          <div class="w-12 h-12 border-4 border-primary/20 border-t-primary rounded-full animate-spin mb-4"></div>
          <p class="text-gray-500 text-sm">{{ loadingMessage }}</p>
        </div>
        <div v-if="summaryText" class="prose prose-slate prose-sm max-w-none summary-prose" v-html="renderedSummary"></div>
        <div v-if="loading && summaryText" class="mt-2 inline-flex items-center gap-1.5 text-xs text-gray-500">
          <span class="w-1.5 h-1.5 bg-primary rounded-full animate-pulse"></span>
          {{ t('summary.generating') }}
        </div>
      </div>

      <!-- 字幕文本 Tab -->
      <div v-show="activeTab === 'subtitle'">
        <div v-if="subtitleData.segments && subtitleData.segments.length > 0">
          <div class="flex items-center justify-between mb-4">
            <div class="text-sm text-gray-500">
              共 {{ (showTranslated ? translatedSegments : subtitleData.segments).length }} 条字幕
              <span v-if="subtitleData.language" class="ml-2 px-2 py-0.5 bg-primary/10 text-primary rounded-full text-xs">
                {{ showTranslated ? currentLang.toUpperCase() : (subtitleData.language || '原始') }}
              </span>
            </div>
            <div class="flex items-center gap-2">
              <button v-if="translatedSegments.length > 0" @click="showTranslated = !showTranslated" class="text-xs text-primary hover:underline">
                {{ showTranslated ? t('subtitle.show_original') : t('subtitle.show_translated') }}
              </button>
              <button v-else-if="!translating" @click="translateSubtitles" class="text-xs text-primary hover:underline flex items-center gap-1">
                🌐 {{ t('subtitle.translate_to') }} {{ currentLang.toUpperCase() }}
              </button>
              <span v-if="translating" class="text-xs text-gray-400">{{ t('subtitle.translating') }}...</span>
              <button @click="subtitleExpanded = !subtitleExpanded" class="text-xs text-primary hover:underline">
                {{ subtitleExpanded ? t('subtitle.collapse') : t('subtitle.expand') }}
              </button>
            </div>
          </div>
          <div :class="['space-y-1 overflow-y-auto', subtitleExpanded ? 'max-h-none' : 'max-h-[500px]']">
            <div v-for="(seg, idx) in (showTranslated ? translatedSegments : subtitleData.segments)" :key="idx" class="flex gap-3 py-2 px-3 rounded-lg hover:bg-gray-50">
              <span class="flex-shrink-0 text-xs text-primary font-mono pt-0.5 min-w-[60px]">{{ formatTime(seg.start) }}</span>
              <span class="text-sm text-gray-800 leading-relaxed">{{ seg.text }}</span>
            </div>
          </div>
        </div>
        <div v-else-if="!loading" class="flex flex-col items-center justify-center py-16 text-gray-500">
          <p v-if="subtitleError === 'rate_limited'" class="text-sm">⚠️ {{ t('subtitle.rate_limited') }}</p>
          <p v-else class="text-sm">{{ t('subtitle.no_subtitles') }}</p>
          <button @click="loadSubtitles" class="mt-3 text-xs text-primary hover:underline">{{ t('common.retry') }}</button>
        </div>
      </div>

      <!-- 思维导图 Tab -->
      <div v-show="activeTab === 'mindmap'">
        <div v-if="mindmapMarkdown" class="relative">
          <div class="flex items-center justify-end gap-2 mb-3">
            <button @click="zoomIn" class="px-3 py-1.5 text-xs border border-gray-300 rounded-lg text-primary hover:bg-primary/10">{{ t('mindmap.zoom_in') }}</button>
            <button @click="zoomOut" class="px-3 py-1.5 text-xs border border-gray-300 rounded-lg text-primary hover:bg-primary/10">{{ t('mindmap.zoom_out') }}</button>
            <button @click="fitView" class="px-3 py-1.5 text-xs border border-gray-300 rounded-lg text-primary hover:bg-primary/10">{{ t('mindmap.fit') }}</button>
            <button @click="toggleFullscreen" class="px-3 py-1.5 text-xs border border-gray-300 rounded-lg text-primary hover:bg-primary/10">
              {{ isFullscreen ? t('mindmap.exit_fullscreen') : t('mindmap.fullscreen') }}
            </button>
            <button @click="downloadMindmapPng" class="px-3 py-1.5 text-xs border border-gray-300 rounded-lg text-primary hover:bg-primary/10">PNG</button>
            <button @click="downloadMindmapSvg" class="px-3 py-1.5 text-xs border border-gray-300 rounded-lg text-primary hover:bg-primary/10">SVG</button>
          </div>
          <div ref="mindmapContainer" class="mindmap-wrapper w-full border border-gray-200 rounded-xl bg-white overflow-hidden"
            :class="isFullscreen ? 'mindmap-fullscreen' : 'min-h-[500px]'">
            <svg ref="mindmapSvg" class="w-full h-full"></svg>
            <button v-if="isFullscreen" @click="toggleFullscreen"
              class="fixed top-4 right-4 z-50 flex items-center gap-1.5 px-4 py-2 rounded-lg bg-white/90 backdrop-blur shadow-lg text-sm text-gray-700 hover:bg-white border border-gray-200">
              {{ t('mindmap.exit_fullscreen') }}
            </button>
          </div>
        </div>
        <div v-else-if="loading" class="flex flex-col items-center justify-center py-16">
          <div class="w-10 h-10 border-4 border-primary/20 border-t-primary rounded-full animate-spin mb-3"></div>
          <p class="text-gray-500 text-sm">{{ t('mindmap.generating') }}</p>
        </div>
        <div v-else class="flex flex-col items-center justify-center py-16 text-gray-500">
          <p class="text-sm">{{ t('mindmap.need_summary') }}</p>
        </div>
      </div>

      <!-- AI 问答 Tab -->
      <div v-show="activeTab === 'qa'">
        <div class="space-y-4 max-h-[400px] overflow-y-auto pr-1">
          <div v-if="chatMessages.length === 0" class="flex flex-col items-center justify-center py-12 text-gray-500">
            <p class="text-sm mb-1">{{ t('qa.empty') }}</p>
            <p class="text-xs">{{ t('qa.example') }}</p>
          </div>
          <div v-for="(msg, idx) in chatMessages" :key="idx" :class="['flex', msg.role === 'user' ? 'justify-end' : 'justify-start']">
            <div :class="[
              'max-w-[80%] px-4 py-2.5 rounded-2xl text-sm leading-relaxed',
              msg.role === 'user' ? 'bg-primary text-white rounded-br-md' : 'bg-gray-100 text-gray-800 rounded-bl-md border border-gray-200'
            ]">
              <span v-if="msg.role === 'user'">{{ msg.content }}</span>
              <div v-else class="chat-prose prose prose-slate prose-sm max-w-none" v-html="renderMarkdown(msg.content)"></div>
              <span v-if="msg.role === 'assistant' && msg.loading" class="inline-block w-1.5 h-4 bg-primary/60 rounded-sm animate-pulse ml-0.5 align-text-bottom"></span>
            </div>
          </div>
        </div>
        <div class="flex gap-2 pt-3 border-t border-gray-200 mt-4">
          <input v-model="chatInput" @keydown.enter.prevent="sendQuestion" type="text" :placeholder="t('qa.placeholder')"
            class="flex-1 h-11 px-4 rounded-xl border border-gray-300 bg-white text-sm text-gray-800 placeholder:text-gray-400 focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary"
            :disabled="chatLoading" />
          <button @click="sendQuestion" :disabled="!chatInput.trim() || chatLoading"
            class="h-11 px-5 rounded-xl bg-primary hover:bg-primary-dark text-white text-sm font-medium disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-1.5">
            <svg v-if="chatLoading" class="animate-spin w-4 h-4" fill="none" viewBox="0 0 24 24">
              <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
              <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"></path>
            </svg>
            {{ t('qa.send') }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, computed, nextTick, onMounted, onBeforeUnmount } from 'vue'
import { marked } from 'marked'
import { Transformer } from 'markmap-lib'
import { Markmap } from 'markmap-view'
import { useI18n } from 'vue-i18n'

const props = defineProps({
  videoUrl: { type: String, required: true },
  videoTitle: { type: String, default: '' },
})

const { locale, t } = useI18n()
// 当前语言代码(映射到后端: zh-CN → zh, en → en, ja → ja)
const currentLang = computed<string>(() => {
  const map: Record<string, string> = { 'zh-CN': 'zh', en: 'en', ja: 'ja' }
  return map[locale.value] || 'en'
})

type TabKey = 'summary' | 'subtitle' | 'mindmap' | 'qa'
const tabs = computed(() => [
  { key: 'summary' as TabKey, label: t('tab.summary'), icon: '📝' },
  { key: 'subtitle' as TabKey, label: t('tab.subtitle'), icon: '📄' },
  { key: 'mindmap' as TabKey, label: t('tab.mindmap'), icon: '🧠' },
  { key: 'qa' as TabKey, label: t('tab.qa'), icon: '💬' },
])

interface SubtitleSegment { start: number; text: string }
interface SubtitleData { segments: SubtitleSegment[]; full_text: string; language?: string; content?: string }
interface ChatMessage { role: 'user' | 'assistant'; content: string; loading?: boolean }

const activeTab = ref<'summary' | 'subtitle' | 'mindmap' | 'qa'>('summary')
const loading = ref(false)
const loadingMessage = ref(t('summary.loadingSubtitles'))
const summaryText = ref('')
const subtitleData = ref<SubtitleData>({ segments: [], full_text: '' })
const subtitleExpanded = ref(false)
const showTranslated = ref(false)
const translating = ref(false)
const translatedSegments = ref<SubtitleSegment[]>([])
const subtitleError = ref<'no_subtitles' | 'rate_limited' | null>(null)
const mindmapMarkdown = ref('')
const mindmapSvg = ref<SVGSVGElement | null>(null)
const mindmapContainer = ref<HTMLDivElement | null>(null)
let markmapInstance: Markmap | null = null
const isFullscreen = ref(false)
const chatMessages = ref<ChatMessage[]>([])
const chatInput = ref('')
const chatLoading = ref(false)
const contentLang = ref(currentLang.value)

marked.setOptions({ breaks: true, gfm: true })

const renderedSummary = computed(() => renderMarkdown(summaryText.value))

// 等总结完成后再生成导图(避免流式累加中只拿到片段)
watch([summaryText, loading], ([text, isLoading]) => {
  if (text && !isLoading && !mindmapMarkdown.value) {
    mindmapMarkdown.value = generateMindmapMarkdown(text)
  }
})

// 数据变化时记录 markdown,等 Tab 切换时再渲染
watch(mindmapMarkdown, (val) => {
  if (val && activeTab.value === 'mindmap') {
    nextTick(() => requestAnimationFrame(() => renderMindmap(val)))
  }
})

// Tab 切换到思维导图时渲染(此时容器可见)
watch(activeTab, (tab) => {
  if (tab === 'mindmap' && mindmapMarkdown.value) {
    nextTick(() => requestAnimationFrame(() => renderMindmap(mindmapMarkdown.value)))
  }
})

function renderMarkdown(text: string) {
  if (!text) return ''
  return marked.parse(text)
}

function formatTime(seconds: number) {
  const m = Math.floor(seconds / 60)
  const s = Math.floor(seconds % 60)
  return `${m}:${String(s).padStart(2, '0')}`
}

function generateMindmapMarkdown(summary: string) {
  const lines = summary.split('\n')
  let nodes = ['# 视频总结']
  for (const line of lines) {
    const trimmed = line.trim()
    if (!trimmed) continue
    // 匹配各种标题格式
    if (trimmed.startsWith('## ') || trimmed.startsWith('### ') || trimmed.startsWith('# ')) {
      nodes.push(trimmed)
    } else if (trimmed.startsWith('- ') || trimmed.startsWith('* ')) {
      nodes.push(trimmed)
    } else if (trimmed.match(/^\d+\.\s+/)) {
      // 数字列表: "1. xxx" → "- xxx"
      nodes.push('- ' + trimmed.replace(/^\d+\.\s+/, ''))
    } else if (trimmed.match(/\*\*[^*]+\*\*[：:]/)) {
      // 加粗标题: "**标题**：内容" → "### 标题"
      const m = trimmed.match(/\*\*([^*]+)\*\*[：:]/)
      if (m) nodes.push('### ' + m[1].trim())
    } else if (trimmed.match(/^[一二三四五六七八九十]+[、\.]/)) {
      // 中文序号: "一、神话起源" → "### 一、神话起源"
      nodes.push('### ' + trimmed)
    } else if (trimmed.length < 40 && !trimmed.includes('，') && !trimmed.includes('。') && !trimmed.includes('、') && !trimmed.includes('：')) {
      // 裸标题: "核心主题"、"关键内容"、"结论"（短行且不含句中标点）
      nodes.push('## ' + trimmed)
    }
    if (nodes.length >= 25) break
  }
  return nodes.join('\n')
}

function renderMindmap(md: string) {
  if (!mindmapSvg.value) return
  // 确保容器有尺寸(v-show 隐藏时 offsetWidth=0 会导致 D3 布局 NaN)
  const parent = mindmapSvg.value.parentElement
  if (!parent || parent.offsetWidth < 10) {
    requestAnimationFrame(() => renderMindmap(md))
    return
  }
  try {
    const transformer = new Transformer()
    const { root } = transformer.transform(md)
    pruneNodes(root, 4)
    if (!markmapInstance) {
      markmapInstance = Markmap.create(mindmapSvg.value, { autoFit: true }, root)
    } else {
      markmapInstance.setData(root)
      markmapInstance.fit()
    }
  } catch (e: any) {
    console.warn('[Mindmap] 渲染失败:', e)
  }
}

function pruneNodes(node: any, maxDepth: number) {
  function walk(n: any, depth: number) {
    if (!n.children) return
    if (depth >= maxDepth) { n.children = []; return }
    for (const child of n.children) walk(child, depth + 1)
  }
  walk(node, 0)
}

function zoomIn() { markmapInstance?.rescale(1.25) }
function zoomOut() { markmapInstance?.rescale(0.8) }
function fitView() { markmapInstance?.fit() }

function toggleFullscreen() {
  if (!mindmapContainer.value) return
  if (!isFullscreen.value) {
    mindmapContainer.value.requestFullscreen?.() || (mindmapContainer.value as any).webkitRequestFullscreen?.()
  } else {
    document.exitFullscreen?.() || (document as any).webkitExitFullscreen?.()
  }
}

function onFullscreenChange() {
  isFullscreen.value = !!document.fullscreenElement
  nextTick(() => markmapInstance?.fit())
}

// ===== 导图导出 =====
function buildExportableSvg() {
  if (!mindmapSvg.value) return null
  const cloned = mindmapSvg.value.cloneNode(true) as Element
  cloned.querySelectorAll('[transform]').forEach((el: Element) => {
    const t = el.getAttribute('transform')
    if (t && t.includes('NaN')) el.setAttribute('transform', 'translate(0,0) scale(1)')
  })
  cloned.querySelectorAll('foreignObject').forEach((fo: Element) => {
    const textContent = fo.textContent?.trim() || ''
    if (!textContent) { fo.remove(); return }
    const x = parseFloat(fo.getAttribute('x') || '0') || 0
    const y = parseFloat(fo.getAttribute('y') || '0') || 0
    const h = parseFloat(fo.getAttribute('height') || '20') || 20
    const textEl = document.createElementNS('http://www.w3.org/2000/svg', 'text')
    textEl.setAttribute('x', String(x + 4))
    textEl.setAttribute('y', String(y + h / 2 + 5))
    textEl.setAttribute('font-size', '14')
    textEl.setAttribute('font-family', 'sans-serif')
    textEl.setAttribute('fill', '#333')
    textEl.setAttribute('dominant-baseline', 'middle')
    textEl.textContent = textContent
    fo.parentNode!.replaceChild(textEl, fo)
  })
  return cloned
}

function serializeSvg(svgEl: Element) {
  const serializer = new XMLSerializer()
  let svgString = serializer.serializeToString(svgEl)
  if (!svgString.includes('xmlns=')) svgString = svgString.replace('<svg', '<svg xmlns="http://www.w3.org/2000/svg"')
  return svgString
}

function setFullViewBox(svgClone: Element) {
  const gRoot = svgClone.querySelector('g')
  let bbox = { x: 0, y: 0, width: 800, height: 600 }
  if (gRoot) { try { bbox = gRoot.getBBox() } catch {} }
  const padding = 60
  svgClone.setAttribute('viewBox', `${bbox.x - padding} ${bbox.y - padding} ${bbox.width + padding * 2} ${bbox.height + padding * 2}`)
  return { vw: bbox.width + padding * 2, vh: bbox.height + padding * 2 }
}

function getSafeFilename() {
  return (props.videoTitle || '视频').replace(/[\\/*?:"<>|]/g, '_').substring(0, 80)
}

function triggerDownload(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url; a.download = filename
  document.body.appendChild(a); a.click(); document.body.removeChild(a)
  URL.revokeObjectURL(url)
}

async function downloadMindmapPng() {
  if (!mindmapSvg.value) return
  const exportSvg = buildExportableSvg() as Element | null
  if (!exportSvg) return
  const { vw, vh } = setFullViewBox(exportSvg)
  const scale = Math.max(4, Math.ceil(3840 / vw))
  const svgString = serializeSvg(exportSvg)
  const canvas = document.createElement('canvas')
  canvas.width = vw * scale; canvas.height = vh * scale
  const ctx = canvas.getContext('2d')!
  ctx.fillStyle = '#ffffff'; ctx.fillRect(0, 0, canvas.width, canvas.height)
  const img = new Image()
  img.onload = () => {
    ctx.drawImage(img, 0, 0, canvas.width, canvas.height)
    canvas.toBlob((blob) => { if (blob) triggerDownload(blob, getSafeFilename() + ' - 思维导图.png') }, 'image/png')
  }
  img.src = 'data:image/svg+xml;base64,' + btoa(unescape(encodeURIComponent(svgString)))
}

function downloadMindmapSvg() {
  if (!mindmapSvg.value) return
  const cloned = mindmapSvg.value.cloneNode(true) as Element
  setFullViewBox(cloned)
  const svgString = serializeSvg(cloned)
  triggerDownload(new Blob([svgString], { type: 'image/svg+xml;charset=utf-8' }), getSafeFilename() + ' - 思维导图.svg')
}

// ===== SSE 加载字幕 + 总结 =====
async function startSummarize() {
  loading.value = true
  summaryText.value = ''
  mindmapMarkdown.value = ''
  loadingMessage.value = '正在提取视频字幕...'

  try {
    // 1. 加载字幕
    const lang = 'auto'
    const apiBase = import.meta.env.VITE_API_URL || ''
    const subResp = await fetch(`${apiBase}/api/videos/subtitles`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url: props.videoUrl, language: lang }),
    })
    if (subResp.ok) {
      const rawData = await subResp.json()
      if (rawData.content) {
        subtitleData.value = {
          segments: parseSrtToSegments(rawData.content),
          full_text: rawData.content,
          language: rawData.language,
        }
        subtitleError.value = null
      } else {
        subtitleData.value = { segments: [], full_text: '', language: rawData.language }
        subtitleError.value = rawData.error || 'no_subtitles'
      }
      loadingMessage.value = 'AI 正在分析视频内容...'
    }

    // 2. SSE 流式总结
    const transcript = subtitleData.value.full_text || `Video title: ${props.videoTitle}.`
    const resp = await fetch(`${apiBase}/api/ai/summary`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ title: props.videoTitle, transcript, language: currentLang.value }),
    })

    if (!resp.ok || !resp.body) throw new Error('总结请求失败')
    const reader = resp.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''
      for (const line of lines) {
        if (!line.startsWith('data: ')) continue
        const raw = line.slice(6).trim()
        if (raw === '[DONE]') { loading.value = false; return }
        try {
          const j = JSON.parse(raw)
          const c = j.choices?.[0]?.delta?.content
          if (c) summaryText.value += c
        } catch {}
      }
    }
    loading.value = false
  } catch (e: any) {
    loading.value = false
    summaryText.value = '总结生成失败: ' + e.message
  }
}

// 加载字幕(可重试)
async function loadSubtitles() {
  subtitleError.value = null
  subtitleData.value = { segments: [], full_text: '' }
  const lang = 'auto'
  try {
    const subResp = await fetch(`${import.meta.env.VITE_API_URL || ''}/api/videos/subtitles`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url: props.videoUrl, language: lang }),
    })
    if (subResp.ok) {
      const rawData = await subResp.json()
      if (rawData.content) {
        subtitleData.value = {
          segments: parseSrtToSegments(rawData.content),
          full_text: rawData.content,
          language: rawData.language,
        }
        subtitleError.value = null
      } else {
        subtitleError.value = rawData.error || 'no_subtitles'
      }
    }
  } catch (e) {
    subtitleError.value = 'rate_limited'
  }
}

// ===== 字幕翻译 =====
async function translateSubtitles() {
  if (!subtitleData.value.full_text || translating.value) return
  translating.value = true
  try {
    const resp = await fetch(`${import.meta.env.VITE_API_URL || ''}/api/subtitles/translate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ content: subtitleData.value.full_text, target_language: currentLang.value }),
    })
    if (!resp.ok) throw new Error(t('subtitle.translate_error'))
    const data = await resp.json()
    if (data.content) {
      translatedSegments.value = parseSrtToSegments(data.content)
      showTranslated.value = true
    }
  } catch (e: any) {
    console.error('Subtitle translation error:', e)
  } finally {
    translating.value = false
  }
}

function parseSrtToSegments(srt: string) {
  const segments: SubtitleSegment[] = []
  const blocks = srt.split(/\n\n+/).filter(Boolean)
  for (const block of blocks) {
    const lines = block.trim().split('\n')
    if (lines.length < 2) continue
    const timeLine = lines[1]
    const m = timeLine.match(/(\d+):(\d+):(\d+)[,.](\d+)\s*-->\s*(\d+):(\d+):(\d+)[,.](\d+)/)
    if (!m) continue
    const start = parseInt(m[1]) * 3600 + parseInt(m[2]) * 60 + parseInt(m[3]) + parseInt(m[4]) / 1000
    const text = lines.slice(2).join(' ').trim()
    if (text) segments.push({ start, text })
  }
  return segments
}

// ===== AI 问答 =====
async function sendQuestion() {
  const question = chatInput.value.trim()
  if (!question || chatLoading.value) return
  chatInput.value = ''
  chatMessages.value.push({ role: 'user' as const, content: question })
  const aiMsg = { role: 'assistant' as const, content: '', loading: true }
  chatMessages.value.push(aiMsg)
  chatLoading.value = true
  try {
    const resp = await fetch(`${import.meta.env.VITE_API_URL || ''}/api/ai/qa`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ transcript: subtitleData.value.full_text || `Video: ${props.videoTitle}`, question, language: currentLang.value }),
    })
    if (!resp.ok || !resp.body) throw new Error('请求失败')
    const reader = resp.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''
      for (const line of lines) {
        if (!line.startsWith('data: ')) continue
        const raw = line.slice(6).trim()
        if (raw === '[DONE]') break
        try {
          const j = JSON.parse(raw)
          const c = j.choices?.[0]?.delta?.content
          if (c) aiMsg.content += c
        } catch {}
      }
    }
    aiMsg.loading = false
  } catch (e: any) {
    aiMsg.content = '回答失败: ' + e.message
    aiMsg.loading = false
  } finally {
    chatLoading.value = false
  }
}

// 语言变化时重新生成总结 + 导图 + 字幕
watch(currentLang, (newLang) => {
  if (!props.videoUrl) return
  // 只有语言真正变化且已加载过内容时才重新生成
  if (newLang === contentLang.value) return
  contentLang.value = newLang
  // 清空旧内容,重新生成
  summaryText.value = ''
  mindmapMarkdown.value = ''
  subtitleData.value = { segments: [], full_text: '' }
  if (markmapInstance && mindmapSvg.value) { mindmapSvg.value.innerHTML = ''; markmapInstance = null }
  startSummarize()
})

onMounted(() => {
  startSummarize()
  document.addEventListener('fullscreenchange', onFullscreenChange)
})

onBeforeUnmount(() => {
  document.removeEventListener('fullscreenchange', onFullscreenChange)
})
</script>

<style scoped>
.summary-prose :deep(h1) { font-size: 1.25rem; font-weight: 700; margin-top: 1rem; margin-bottom: 0.5rem; }
.summary-prose :deep(h2) { font-size: 1.125rem; font-weight: 700; margin-top: 1rem; margin-bottom: 0.5rem; }
.summary-prose :deep(h3) { font-size: 1rem; font-weight: 600; margin-top: 0.75rem; margin-bottom: 0.5rem; }
.summary-prose :deep(p) { margin-bottom: 0.5rem; line-height: 1.8; }
.summary-prose :deep(ul), .summary-prose :deep(ol) { margin-bottom: 0.5rem; padding-left: 1.5rem; }
.summary-prose :deep(li) { margin-bottom: 0.25rem; line-height: 1.8; }
.summary-prose :deep(li::marker) { color: var(--color-primary); }
.chat-prose :deep(p) { margin-bottom: 0.25rem; line-height: 1.7; }
.chat-prose :deep(ul), .chat-prose :deep(ol) { padding-left: 1.25rem; }
.mindmap-fullscreen { position: fixed !important; top: 0; left: 0; right: 0; bottom: 0; z-index: 40; border-radius: 0 !important; border: none !important; background: #ffffff; }
.mindmap-wrapper :deep(foreignObject) { overflow: visible !important; }
</style>
