<script setup>
import { onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useProjectStore } from '@/stores/project.js'
import EmptyState from '@/components/EmptyState.vue'
import { Plus } from 'lucide-vue-next'

const router = useRouter()
const store = useProjectStore()

onMounted(() => {
  store.fetchProjects()
})

function formatDate(dateStr) {
  return new Date(dateStr).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
}

const statusColors = {
  created: { bg: 'var(--border)', color: 'var(--text-secondary)' },
  graph_built: { bg: 'var(--accent)', color: 'white' },
  completed: { bg: 'var(--success)', color: 'white' },
}
</script>

<template>
  <div class="p-10 max-w-6xl mx-auto">
    <div class="flex items-center justify-between mb-8">
      <h1 class="text-2xl font-bold" :style="{ fontFamily: 'var(--font-display)', color: 'var(--text-primary)' }">Projects</h1>
      <button
        v-if="store.projects.length"
        class="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium text-white"
        :style="{ backgroundColor: 'var(--accent)' }"
        @click="router.push('/projects/new')"
      >
        <Plus :size="16" /> New Project
      </button>
    </div>

    <EmptyState
      v-if="!store.projects.length"
      icon="FolderOpen"
      title="No projects yet"
      description="Create your first prediction project to get started."
      actionLabel="New Project"
      @action="router.push('/projects/new')"
    />

    <div v-else class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
      <div
        v-for="project in store.projects"
        :key="project.id"
        class="rounded-xl border p-5 cursor-pointer transition-all"
        :style="{
          backgroundColor: 'var(--surface-raised)',
          borderColor: 'var(--border)',
          boxShadow: 'var(--shadow-sm)',
        }"
        @mouseenter="$el.style.transform = 'translateY(-2px)'; $el.style.boxShadow = 'var(--shadow-md)'"
        @mouseleave="$el.style.transform = ''; $el.style.boxShadow = 'var(--shadow-sm)'"
        @click="router.push(`/projects/${project.id}/overview`)"
      >
        <div class="flex items-center gap-2 mb-3">
          <h3 class="text-lg font-semibold flex-1 truncate" :style="{ fontFamily: 'var(--font-display)', color: 'var(--text-primary)' }">
            {{ project.name }}
          </h3>
          <span
            class="text-xs px-2 py-0.5 rounded-full font-medium shrink-0"
            :style="{ backgroundColor: (statusColors[project.status] || statusColors.created).bg, color: (statusColors[project.status] || statusColors.created).color }"
          >{{ project.status }}</span>
        </div>
        <div class="flex items-center gap-2 mb-2">
          <span class="text-xs px-2 py-0.5 rounded" :style="{ backgroundColor: 'var(--accent-surface)', color: 'var(--accent)' }">
            {{ project.domain }}
          </span>
        </div>
        <p class="text-sm truncate" :style="{ color: 'var(--text-secondary)' }">{{ project.requirement }}</p>
        <div class="mt-3 text-xs" :style="{ color: 'var(--text-tertiary)', fontFamily: 'var(--font-mono)' }">
          {{ formatDate(project.created_at) }}
          <span v-if="project.files">&nbsp;· {{ project.files.length }} files</span>
        </div>
      </div>
    </div>
  </div>
</template>
