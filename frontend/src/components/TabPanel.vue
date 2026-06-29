<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  tabs: { key: string; label: string }[]
  modelValue?: string
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', key: string): void
}>()

const activeTab = computed({
  get: () => props.modelValue ?? props.tabs[0]?.key ?? '',
  set: (key: string) => emit('update:modelValue', key),
})
</script>

<template>
  <div>
    <nav class="relative flex border-b border-gray-200">
      <button
        v-for="tab in tabs"
        :key="tab.key"
        type="button"
        class="relative px-5 py-3 text-sm transition-colors"
        :class="
          activeTab === tab.key
            ? 'text-primary font-medium'
            : 'text-gray-500 hover:text-gray-700'
        "
        @click="activeTab = tab.key"
      >
        {{ tab.label }}
        <span
          v-if="activeTab === tab.key"
          class="absolute bottom-0 left-0 right-0 h-0.5 bg-primary"
        />
      </button>
    </nav>
    <div>
      <slot :name="activeTab" />
    </div>
  </div>
</template>
