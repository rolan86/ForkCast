<script setup>
import { onMounted, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useProjectStore } from '@/stores/project.js'
import { BarChart3, GitBranch, Play } from 'lucide-vue-next'

const route = useRoute()
const router = useRouter()
const store = useProjectStore()

const projectId = computed(() => route.params.id)

onMounted(async () => {
  await store.fetchProject(projectId.value)
  await Promise.all([
    store.fetchGraph(projectId.value),
    store.fetchSimulations(),
  ])
})

const tabs = [
  { name: 'project-overview', label: 'Overview', icon: BarChart3 },
  { name: 'project-graph', label: 'Graph', icon: GitBranch },
  { name: 'project-simulations', label: 'Simulations', icon: Play },
]

const graphActive = computed(() => !!store.graphBuildProgress?.stage && store.graphBuildProgress.stage !== 'complete')
const simActive = computed(() => {
  const stage = store.simPrepareProgress?.stage || store.simRunProgress?.stage
  return !!stage && stage !== 'complete' && stage !== 'result'
})
function isTabActive(tabName) {
  if (tabName === 'project-graph') return graphActive.value
  if (tabName === 'project-simulations') return simActive.value
  return false
}

const activeTab = computed(() => route.name)
</script>

<template>
  <div class="h-full flex flex-col">
    <div class="px-6 pt-6 pb-0" :style="{ borderBottom: '1px solid var(--border)' }">
      <h1
        v-if="store.currentProject"
        class="text-2xl font-bold mb-4"
        :style="{ fontFamily: 'var(--font-display)', color: 'var(--text-primary)' }"
      >{{ store.currentProject.name }}</h1>

      <nav class="flex gap-1">
        <button
          v-for="tab in tabs"
          :key="tab.name"
          class="flex items-center gap-2 px-4 py-2.5 text-sm font-medium rounded-t-lg transition-colors relative"
          :style="{
            color: activeTab === tab.name ? 'var(--accent)' : 'var(--text-secondary)',
            backgroundColor: activeTab === tab.name ? 'var(--accent-surface)' : 'transparent',
          }"
          @click="router.push({ name: tab.name, params: { id: projectId } })"
          @mouseenter="activeTab !== tab.name && ($el.style.color = 'var(--text-primary)')"
          @mouseleave="activeTab !== tab.name && ($el.style.color = 'var(--text-secondary)')"
        >
          <component :is="tab.icon" :size="16" />
          {{ tab.label }}
          <span
            v-if="isTabActive(tab.name)"
            class="w-2 h-2 rounded-full animate-pulse"
            :style="{ backgroundColor: 'var(--warning)' }"
          />
          <div
            v-if="activeTab === tab.name"
            class="absolute bottom-0 left-0 right-0 h-0.5"
            :style="{ backgroundColor: 'var(--accent)' }"
          />
        </button>
      </nav>
    </div>

    <div class="flex-1 overflow-auto">
      <RouterView />
    </div>
  </div>
</template>
