<script setup lang="ts">
import { onMounted, onUnmounted } from 'vue'
import { useAuthStore } from '@/stores/auth'
import WorkshopPage from '@/pages/WorkshopPage.vue'

const authStore = useAuthStore()

onMounted(() => {
  authStore.initialize()
})

onUnmounted(() => {
  authStore.cleanup()
})
</script>

<template>
  <WorkshopPage />
</template>
