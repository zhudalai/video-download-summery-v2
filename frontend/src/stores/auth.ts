import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { supabase } from '@/lib/supabaseClient'
import type { User, Session, Provider } from '@supabase/supabase-js'

export const useAuthStore = defineStore('auth', () => {
  const user = ref<User | null>(null)
  const session = ref<Session | null>(null)
  const loading = ref(true)
  const initialized = ref(false)

  let unsubscribe: (() => void) | null = null

  const isAuthenticated = computed(() => !!user.value)
  const userId = computed(() => user.value?.id)
  const userEmail = computed(() => user.value?.email)
  const userRole = computed(() => user.value?.role ?? 'authenticated')

  const initialize = async () => {
    if (initialized.value) return

    try {
      const { data: { session: currentSession } } = await supabase.auth.getSession()
      session.value = currentSession
      user.value = currentSession?.user ?? null
    } catch (error) {
      console.error('Failed to get session:', error)
    } finally {
      loading.value = false
    }

    const { data } = supabase.auth.onAuthStateChange((_event, newSession) => {
      session.value = newSession
      user.value = newSession?.user ?? null
    })
    unsubscribe = data.subscription.unsubscribe
    initialized.value = true
  }

  const signInWithPassword = async (email: string, password: string) => {
    loading.value = true
    try {
      const { data, error } = await supabase.auth.signInWithPassword({ email, password })
      return { data, error }
    } finally {
      loading.value = false
    }
  }

  const signUp = async (email: string, password: string) => {
    loading.value = true
    try {
      const { data, error } = await supabase.auth.signUp({
        email,
        password,
        options: {
          emailRedirectTo: `${window.location.origin}/auth/callback`
        }
      })
      return { data, error }
    } finally {
      loading.value = false
    }
  }

  const signInWithOAuth = async (provider: Provider) => {
    const { error } = await supabase.auth.signInWithOAuth({
      provider,
      options: {
        redirectTo: `${window.location.origin}/auth/callback`
      }
    })
    return { error }
  }

  const signInWithOtp = async (email: string) => {
    const { error } = await supabase.auth.signInWithOtp({
      email,
      options: {
        emailRedirectTo: `${window.location.origin}/auth/callback`
      }
    })
    return { error }
  }

  const verifyOtp = async (token_hash: string, type: string) => {
    const { data, error } = await supabase.auth.verifyOtp({
      token_hash,
      type: type as any
    })
    return { data, error }
  }

  const signOut = async () => {
    const { error } = await supabase.auth.signOut()
    user.value = null
    session.value = null
    return { error }
  }

  const cleanup = () => {
    unsubscribe?.()
    unsubscribe = null
    initialized.value = false
  }

  return {
    user, session, loading, initialized,
    isAuthenticated, userId, userEmail, userRole,
    initialize, signInWithPassword, signUp, signInWithOAuth,
    signInWithOtp, verifyOtp, signOut, cleanup
  }
})
