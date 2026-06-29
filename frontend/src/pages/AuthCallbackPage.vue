<script setup lang="ts">
import { onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const authStore = useAuthStore()

onMounted(async () => {
  // Supabase SDK 自动处理 PKCE code exchange
  // 这里等待 authStore 的 onAuthStateChange 回调更新 user
  await new Promise(resolve => setTimeout(resolve, 1000))

  if (authStore.isAuthenticated) {
    router.push({ name: 'home' })
  } else {
    router.push({ name: 'login' })
  }
})
</script>

<template>
  <div class="min-h-screen flex items-center justify-center">
    <div class="text-center">
      <div class="animate-spin rounded-full h-12 w-12 border-b-2 border-primary mx-auto mb-4"></div>
      <p class="text-gray-600">Completing sign in...</p>
    </div>
  </div>
</template>
