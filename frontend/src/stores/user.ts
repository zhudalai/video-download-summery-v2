import { defineStore } from 'pinia'
import { computed } from 'vue'
import { useAuthStore } from './auth'

export const useUserStore = defineStore('user', () => {
  const authStore = useAuthStore()

  const user = computed(() => authStore.user)
  const isAuthenticated = computed(() => authStore.isAuthenticated)
  const isVip = computed(() => user.value?.role === 'pro' || user.value?.role === 'premium')

  async function fetchUser() {
    // 用户信息直接从 Supabase Auth session 获取
    // 业务用户数据(如 language/currency/role)需要从后端 API 获取
  }

  async function logout() {
    await authStore.signOut()
  }

  return { user, isAuthenticated, isVip, fetchUser, logout }
})
