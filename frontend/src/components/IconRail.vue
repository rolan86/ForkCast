<script setup>
import { ref } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { FolderOpen, Globe, Sun, Moon } from 'lucide-vue-next'
import { theme, toggleTheme } from '@/lib/theme.js'
import { useProjectStore } from '@/stores/project.js'

const router = useRouter()
const route = useRoute()
const store = useProjectStore()
const expanded = ref(false)

let expandTimeout = null
function onMouseEnter() {
  expandTimeout = setTimeout(() => { expanded.value = true }, 60)
}
function onMouseLeave() {
  clearTimeout(expandTimeout)
  expanded.value = false
}

function navigate(path) {
  router.push(path)
}
</script>

<template>
  <nav
    class="h-screen flex flex-col border-r transition-all"
    :class="expanded ? 'w-[200px]' : 'w-12'"
    :style="{
      borderColor: 'var(--border)',
      backgroundColor: 'var(--surface-raised)',
      transitionDuration: expanded ? 'var(--duration-normal)' : '150ms',
      transitionTimingFunction: 'var(--ease-out)',
    }"
    @mouseenter="onMouseEnter"
    @mouseleave="onMouseLeave"
  >
    <!-- Logo -->
    <div class="h-12 flex items-center justify-center shrink-0 border-b" :style="{ borderColor: 'var(--border)' }">
      <span class="text-lg font-bold" :style="{ fontFamily: 'var(--font-display)', color: 'var(--accent)' }">F</span>
      <span
        v-if="expanded"
        class="ml-1 text-sm font-semibold overflow-hidden whitespace-nowrap"
        :style="{ fontFamily: 'var(--font-display)', color: 'var(--text-primary)', opacity: expanded ? 1 : 0, transition: 'opacity 100ms 100ms' }"
      >orkCast</span>
    </div>

    <!-- Nav items -->
    <div class="flex-1 flex flex-col gap-1 p-2">
      <button
        class="flex items-center gap-3 px-2 py-2 rounded-lg transition-colors"
        :style="{
          backgroundColor: route.path.startsWith('/projects') ? 'var(--accent-surface)' : 'transparent',
          color: route.path.startsWith('/projects') ? 'var(--accent)' : 'var(--text-secondary)',
        }"
        @click="navigate('/projects')"
      >
        <FolderOpen :size="20" class="shrink-0" />
        <span v-if="expanded" class="text-sm truncate">Projects</span>
      </button>
      <button
        class="flex items-center gap-3 px-2 py-2 rounded-lg transition-colors opacity-50 cursor-not-allowed"
        :style="{ color: 'var(--text-secondary)' }"
        title="Domain management available in Phase 7c"
      >
        <Globe :size="20" class="shrink-0" />
        <span v-if="expanded" class="text-sm truncate">Domains</span>
      </button>
    </div>

    <!-- Bottom: theme toggle -->
    <div class="p-2 border-t" :style="{ borderColor: 'var(--border)' }">
      <button
        class="flex items-center gap-3 px-2 py-2 rounded-lg w-full transition-colors hover:opacity-80"
        :style="{ color: 'var(--text-secondary)' }"
        @click="toggleTheme"
      >
        <Sun v-if="theme === 'dark'" :size="20" class="shrink-0" />
        <Moon v-else :size="20" class="shrink-0" />
        <span v-if="expanded" class="text-sm truncate">{{ theme === 'dark' ? 'Light mode' : 'Dark mode' }}</span>
      </button>
    </div>
  </nav>
</template>
