<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import LanguageSwitcher from '@/components/LanguageSwitcher.vue'

const { t } = useI18n()
const router = useRouter()
const authStore = useAuthStore()

const handleLogout = async () => {
  await authStore.signOut()
  router.push({ name: 'home' })
}
</script>

<template>
  <div class="min-h-screen flex flex-col">
    <header class="bg-white shadow-sm">
      <nav class="max-w-7xl mx-auto px-4 h-16 flex items-center justify-between">
        <router-link to="/" class="text-xl font-bold text-primary">{{ t('common.appName') }}</router-link>
        <div class="flex items-center gap-6">
          <template v-if="authStore.isAuthenticated">
            <router-link to="/download">{{ t('nav.download') }}</router-link>
            <router-link to="/billing">{{ t('nav.billing') }}</router-link>
            <LanguageSwitcher />
            <span class="text-sm text-gray-600">{{ authStore.userEmail }}</span>
            <button @click="handleLogout" class="text-sm text-gray-600 hover:text-gray-900">
              {{ t('nav.logout') }}
            </button>
          </template>
          <template v-else>
            <router-link to="/download">{{ t('nav.download') }}</router-link>
            <LanguageSwitcher />
            <router-link to="/login" class="text-sm text-gray-600 hover:text-gray-900">{{ t('nav.login') }}</router-link>
            <router-link to="/login?mode=signup" class="btn-primary">{{ t('nav.signup') }}</router-link>
          </template>
        </div>
      </nav>
    </header>
    <main class="flex-1">
      <router-view />
    </main>
  </div>
</template>
