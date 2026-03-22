/**
 * Dark/light mode management.
 * Stored in localStorage('forkcast-theme'). Falls back to prefers-color-scheme.
 */
import { ref, watchEffect } from 'vue'

const STORAGE_KEY = 'forkcast-theme'

function getInitialTheme() {
  const stored = localStorage.getItem(STORAGE_KEY)
  if (stored === 'dark' || stored === 'light') return stored
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
}

export const theme = ref(getInitialTheme())

watchEffect(() => {
  const html = document.documentElement
  html.classList.toggle('dark', theme.value === 'dark')
  localStorage.setItem(STORAGE_KEY, theme.value)
})

export function toggleTheme() {
  theme.value = theme.value === 'dark' ? 'light' : 'dark'
}
