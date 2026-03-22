<script setup>
import { computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useProjectStore } from '@/stores/project.js'
import StatCard from '@/components/StatCard.vue'
import EmptyState from '@/components/EmptyState.vue'

const router = useRouter()
const route = useRoute()
const store = useProjectStore()

const project = computed(() => store.currentProject)
const graph = computed(() => store.currentGraph)
const sims = computed(() => store.projectSimulations)

const fileCount = computed(() => project.value?.files?.length || 0)
const entityCount = computed(() => graph.value?.node_count || 0)
const edgeCount = computed(() => graph.value?.edge_count || 0)
const simCount = computed(() => sims.value.length)
const latestSim = computed(() => sims.value[0] || null)
const graphBuilt = computed(() => !!graph.value && graph.value.status === 'built')

function goToGraph() {
  router.push({ name: 'project-graph', params: { id: route.params.id } })
}
function goToSimulations() {
  router.push({ name: 'project-simulations', params: { id: route.params.id } })
}

function formatRelative(dateStr) {
  if (!dateStr) return ''
  const diff = Date.now() - new Date(dateStr).getTime()
  const mins = Math.floor(diff / 60000)
  if (mins < 60) return `${mins}m ago`
  const hours = Math.floor(mins / 60)
  if (hours < 24) return `${hours}h ago`
  return `${Math.floor(hours / 24)}d ago`
}

const nextAction = computed(() => {
  if (!graphBuilt.value) return { label: 'Build Graph', action: goToGraph }
  if (!sims.value.length) return { label: 'Prepare Simulation', action: goToSimulations }
  return { label: 'Generate Report', action: () => {}, disabled: true }
})
</script>

<template>
  <div class="p-6 space-y-6">
    <div class="grid grid-cols-3 gap-4">
      <StatCard label="Documents" :value="fileCount" icon="FileText" />
      <StatCard
        label="Graph"
        :value="entityCount"
        :subtitle="graphBuilt ? `${edgeCount} relationships` : 'Not built'"
        icon="GitBranch"
      />
      <StatCard
        label="Simulations"
        :value="simCount"
        :subtitle="latestSim ? latestSim.status : 'None'"
        icon="Play"
      />
    </div>

    <div class="grid grid-cols-5 gap-6">
      <div class="col-span-3 rounded-xl border p-5" :style="{ borderColor: 'var(--border)', backgroundColor: 'var(--surface-raised)' }">
        <div class="flex items-center justify-between mb-4">
          <h3 class="text-lg font-semibold" :style="{ fontFamily: 'var(--font-display)', color: 'var(--text-primary)' }">Knowledge Graph</h3>
          <button
            v-if="graphBuilt"
            class="text-sm"
            :style="{ color: 'var(--accent)' }"
            @click="goToGraph"
            @mouseenter="$el.style.textDecoration = 'underline'"
            @mouseleave="$el.style.textDecoration = ''"
          >View Full Graph →</button>
        </div>
        <EmptyState
          v-if="!graphBuilt"
          icon="GitBranch"
          title="No knowledge graph yet"
          description="Upload documents and build a graph to visualize entities and relationships."
          actionLabel="Build Graph"
          @action="goToGraph"
        />
        <div v-else class="h-48 rounded-lg flex items-center justify-center" :style="{ backgroundColor: 'var(--surface-sunken)' }">
          <p class="text-sm" :style="{ color: 'var(--text-tertiary)' }">Graph preview — {{ entityCount }} entities, {{ edgeCount }} edges</p>
        </div>
      </div>

      <div class="col-span-2 space-y-4">
        <div class="rounded-xl border p-5" :style="{ borderColor: 'var(--border)', backgroundColor: 'var(--surface-raised)' }">
          <h3 class="text-xs uppercase tracking-wider mb-3" :style="{ color: 'var(--text-secondary)', fontFamily: 'var(--font-mono)', letterSpacing: '0.5px' }">Next Step</h3>
          <button
            class="w-full py-2.5 rounded-lg text-sm font-medium text-white"
            :style="{ backgroundColor: nextAction.disabled ? 'var(--text-tertiary)' : 'var(--accent)', cursor: nextAction.disabled ? 'not-allowed' : 'pointer' }"
            :disabled="nextAction.disabled"
            @click="nextAction.action"
          >{{ nextAction.label }}</button>
        </div>

        <div class="rounded-xl border p-5" :style="{ borderColor: 'var(--border)', backgroundColor: 'var(--surface-raised)' }">
          <h3 class="text-xs uppercase tracking-wider mb-3" :style="{ color: 'var(--text-secondary)', fontFamily: 'var(--font-mono)', letterSpacing: '0.5px' }">Recent Activity</h3>
          <div v-if="!sims.length && !graphBuilt" class="text-sm py-4 text-center" :style="{ color: 'var(--text-tertiary)' }">
            No activity yet. Start by building a knowledge graph.
          </div>
          <div v-else class="space-y-3">
            <div v-if="graphBuilt" class="flex items-start gap-3">
              <div class="w-2 h-2 rounded-full mt-1.5 shrink-0" :style="{ backgroundColor: 'var(--success)' }" />
              <div>
                <p class="text-sm" :style="{ color: 'var(--text-primary)' }">Knowledge graph built</p>
                <p class="text-xs" :style="{ color: 'var(--text-tertiary)' }">{{ entityCount }} entities</p>
              </div>
            </div>
            <div v-for="sim in sims.slice(0, 3)" :key="sim.id" class="flex items-start gap-3 cursor-pointer" @click="goToSimulations">
              <div
                class="w-2 h-2 rounded-full mt-1.5 shrink-0"
                :style="{ backgroundColor: sim.status === 'completed' ? 'var(--success)' : 'var(--warning)' }"
              />
              <div>
                <p class="text-sm" :style="{ color: 'var(--text-primary)' }">Simulation {{ sim.status }}</p>
                <p class="text-xs" :style="{ color: 'var(--text-tertiary)' }">{{ formatRelative(sim.updated_at || sim.created_at) }}</p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
