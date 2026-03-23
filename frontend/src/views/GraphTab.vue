<script setup>
import { ref, computed, onMounted, onUnmounted, watch, nextTick } from 'vue'
import { useRoute } from 'vue-router'
import { useProjectStore } from '@/stores/project.js'
import { buildGraph, getGraphData, streamGraphBuild } from '@/api/graphs.js'
import EmptyState from '@/components/EmptyState.vue'
import ProgressPanel from '@/components/ProgressPanel.vue'
import ConfirmModal from '@/components/ConfirmModal.vue'
import { Search, Plus, Minus, RotateCcw } from 'lucide-vue-next'
import * as d3 from 'd3'

const route = useRoute()
const store = useProjectStore()
const projectId = computed(() => route.params.id)

// State: 'empty' | 'building' | 'ready'
const viewState = ref('empty')
const buildError = ref('')
const buildDisconnected = ref(false)
const showRebuildModal = ref(false)
const graphData = ref(null)
const selectedNode = ref(null)
const searchQuery = ref('')
const activeFilters = ref([])

// D3 refs
const svgContainer = ref(null)
let simulation = null
let sseConnection = null

const GRAPH_BUILD_STEPS = [
  { label: 'Extract text', stageNames: ['extracting_text'] },
  { label: 'Chunk', stageNames: ['chunking'] },
  { label: 'Ontology', stageNames: ['generating_ontology'] },
  { label: 'Entities', stageNames: ['extracting_entities', 'deduplicating'] },
  { label: 'Build graph', stageNames: ['building_graph', 'indexing', 'registering'] },
]

const NODE_COLORS = {
  Person: '#3b82f6',
  Organization: '#8b5cf6',
  Concept: '#6366f1',
  Topic: '#10b981',
  Event: '#f59e0b',
}

onMounted(() => {
  if (store.currentGraph && (store.currentGraph.status === 'complete' || store.currentGraph.status === 'built')) {
    loadGraphData()
  } else {
    viewState.value = 'empty'
  }
})

onUnmounted(() => {
  sseConnection?.close()
  simulation?.stop()
})

async function loadGraphData() {
  try {
    graphData.value = await getGraphData(projectId.value)
    viewState.value = 'ready'
    await nextTick()
    renderGraph()
  } catch {
    viewState.value = 'empty'
  }
}

function startBuild() {
  viewState.value = 'building'
  buildError.value = ''
  buildDisconnected.value = false
  store.resetGraphBuildProgress()

  buildGraph(projectId.value).catch(err => {
    if (!buildError.value) buildError.value = err.message || 'Build failed'
  })

  sseConnection = streamGraphBuild(projectId.value, {
    onMessage(data) {
      buildDisconnected.value = false
      store.updateGraphBuildProgress(data)
    },
    onError(message) {
      buildError.value = message
    },
    async onComplete() {
      await store.fetchGraph(projectId.value)
      await loadGraphData()
    },
    onDisconnect() {
      buildDisconnected.value = true
    },
  })
}

function cancelBuild() {
  sseConnection?.close()
  viewState.value = 'empty'
}

function retryBuild() {
  sseConnection?.close()
  startBuild()
}

function confirmRebuild() {
  showRebuildModal.value = false
  startBuild()
}

function renderGraph() {
  if (!svgContainer.value || !graphData.value) return

  const container = svgContainer.value
  const width = container.clientWidth
  const height = container.clientHeight || 500

  d3.select(container).selectAll('*').remove()

  const svg = d3.select(container)
    .append('svg')
    .attr('width', width)
    .attr('height', height)
    .attr('viewBox', [0, 0, width, height])

  const g = svg.append('g')
  let currentZoomScale = 1

  const zoom = d3.zoom()
    .scaleExtent([0.3, 5])
    .on('zoom', (event) => {
      g.attr('transform', event.transform)
      currentZoomScale = event.transform.k
      g.selectAll('.node-label').attr('display', currentZoomScale > 1.5 ? 'block' : 'none')
    })
  svg.call(zoom)

  const nodes = graphData.value.nodes.map(n => ({ ...n }))
  const edges = graphData.value.edges.map(e => ({ ...e }))

  _connCounts = {}
  edges.forEach(e => {
    _connCounts[e.source] = (_connCounts[e.source] || 0) + 1
    _connCounts[e.target] = (_connCounts[e.target] || 0) + 1
  })

  function nodeRadius(id) {
    return nodeRadiusFor(id)
  }

  const useCanvas = nodes.length > 150

  if (useCanvas) {
    simulation = d3.forceSimulation(nodes)
      .force('link', d3.forceLink(edges).id(d => d.id).distance(80))
      .force('charge', d3.forceManyBody().strength(-200))
      .force('center', d3.forceCenter(width / 2, height / 2))
      .force('collide', d3.forceCollide().radius(d => nodeRadius(d.id) + 8))
      .stop()

    for (let i = 0; i < 300; i++) simulation.tick()

    g.selectAll('line')
      .data(edges)
      .join('line')
      .attr('x1', d => d.source.x)
      .attr('y1', d => d.source.y)
      .attr('x2', d => d.target.x)
      .attr('y2', d => d.target.y)
      .attr('stroke', 'var(--border)')
      .attr('stroke-width', 1)

    g.selectAll('circle')
      .data(nodes)
      .join('circle')
      .attr('cx', d => d.x)
      .attr('cy', d => d.y)
      .attr('r', d => nodeRadius(d.id))
      .attr('fill', d => NODE_COLORS[d.type] || '#6366f1')
      .attr('opacity', 0.85)
      .on('click', (event, d) => selectNode(d))
  } else {
    simulation = d3.forceSimulation(nodes)
      .force('link', d3.forceLink(edges).id(d => d.id).distance(80))
      .force('charge', d3.forceManyBody().strength(-200))
      .force('center', d3.forceCenter(width / 2, height / 2))
      .force('collide', d3.forceCollide().radius(d => nodeRadius(d.id) + 8))
      .alphaDecay(0.02)
      .velocityDecay(0.4)

    const link = g.selectAll('line')
      .data(edges)
      .join('line')
      .attr('stroke', 'var(--border)')
      .attr('stroke-width', 1)

    const node = g.selectAll('circle')
      .data(nodes)
      .join('circle')
      .attr('r', d => nodeRadius(d.id))
      .attr('fill', d => NODE_COLORS[d.type] || '#6366f1')
      .attr('opacity', 0.85)
      .attr('cursor', 'pointer')
      .on('click', (event, d) => selectNode(d))
      .call(d3.drag()
        .on('start', (event, d) => { if (!event.active) simulation.alphaTarget(0.3).restart(); d.fx = d.x; d.fy = d.y })
        .on('drag', (event, d) => { d.fx = event.x; d.fy = event.y })
        .on('end', (event, d) => { if (!event.active) simulation.alphaTarget(0); d.fx = null; d.fy = null })
      )

    node.append('title').text(d => `${d.id} (${d.type})`)

    const labels = g.selectAll('.node-label')
      .data(nodes)
      .join('text')
      .attr('class', 'node-label')
      .attr('display', 'none')
      .attr('font-size', '10px')
      .attr('font-family', 'var(--font-mono)')
      .attr('fill', 'var(--text-primary)')
      .attr('dx', d => nodeRadius(d.id) + 4)
      .attr('dy', 4)
      .text(d => d.id)

    simulation.on('tick', () => {
      link
        .attr('x1', d => d.source.x).attr('y1', d => d.source.y)
        .attr('x2', d => d.target.x).attr('y2', d => d.target.y)
      node
        .attr('cx', d => d.x).attr('cy', d => d.y)
      labels
        .attr('x', d => d.x).attr('y', d => d.y)
    })

    node.attr('opacity', 0)
      .transition()
      .delay((d, i) => 500 + i * 20)
      .duration(200)
      .attr('opacity', 0.85)
  }
}

function selectNode(d) {
  selectedNode.value = {
    ...d,
    connections: graphData.value.edges
      .filter(e => (e.source.id || e.source) === d.id || (e.target.id || e.target) === d.id)
      .map(e => ({
        node: (e.source.id || e.source) === d.id ? (e.target.id || e.target) : (e.source.id || e.source),
        label: e.label,
        type: graphData.value.nodes.find(n => n.id === ((e.source.id || e.source) === d.id ? (e.target.id || e.target) : (e.source.id || e.source)))?.type,
      })),
  }
}

function closeDetail() {
  selectedNode.value = null
}

const entityTypes = computed(() => {
  if (!graphData.value) return []
  return [...new Set(graphData.value.nodes.map(n => n.type).filter(Boolean))]
})

function toggleFilter(type) {
  const idx = activeFilters.value.indexOf(type)
  if (idx >= 0) activeFilters.value.splice(idx, 1)
  else activeFilters.value.push(type)
}

// Wire search + filters into D3 visualization
function applySearchAndFilters() {
  if (!svgContainer.value || !graphData.value) return
  const container = d3.select(svgContainer.value)
  const query = searchQuery.value.toLowerCase().trim()
  const filters = activeFilters.value

  container.selectAll('circle').each(function (d) {
    const matchesSearch = !query || d.id.toLowerCase().includes(query) || (d.type || '').toLowerCase().includes(query)
    const matchesFilter = !filters.length || filters.includes(d.type)
    const visible = matchesSearch && matchesFilter
    d3.select(this)
      .attr('opacity', visible ? 0.85 : 0.1)
      .attr('r', visible && query && d.id.toLowerCase().includes(query) ? nodeRadiusFor(d.id) * 1.5 : nodeRadiusFor(d.id))
  })
  container.selectAll('.node-label').each(function (d) {
    const matchesSearch = !query || d.id.toLowerCase().includes(query) || (d.type || '').toLowerCase().includes(query)
    const matchesFilter = !filters.length || filters.includes(d.type)
    d3.select(this).attr('opacity', matchesSearch && matchesFilter ? 1 : 0.1)
  })
  container.selectAll('line').each(function (d) {
    const srcId = d.source.id || d.source
    const tgtId = d.target.id || d.target
    const srcNode = graphData.value.nodes.find(n => n.id === srcId)
    const tgtNode = graphData.value.nodes.find(n => n.id === tgtId)
    const srcMatch = (!query || srcId.toLowerCase().includes(query)) && (!filters.length || filters.includes(srcNode?.type))
    const tgtMatch = (!query || tgtId.toLowerCase().includes(query)) && (!filters.length || filters.includes(tgtNode?.type))
    d3.select(this).attr('opacity', srcMatch || tgtMatch ? 1 : 0.05)
  })
}

// Store nodeRadius function for reuse in search highlighting
let _connCounts = {}
function nodeRadiusFor(id) {
  return 8 + Math.min((_connCounts[id] || 0) * 1.5, 12)
}

watch([searchQuery, activeFilters], applySearchAndFilters, { deep: true })
</script>

<template>
  <!-- Empty state -->
  <div v-if="viewState === 'empty'" class="p-6">
    <EmptyState
      icon="GitBranch"
      title="No knowledge graph"
      description="Upload documents and build a graph to visualize entities and relationships."
      actionLabel="Build Graph"
      @action="startBuild"
    />
  </div>

  <!-- Building state -->
  <div v-else-if="viewState === 'building'" class="p-6">
    <ProgressPanel
      title="Building Knowledge Graph..."
      :steps="GRAPH_BUILD_STEPS"
      :currentStage="store.graphBuildProgress?.stage || ''"
      :progress="{ current: store.graphBuildProgress?.current, total: store.graphBuildProgress?.total }"
      :logEntries="store.graphBuildProgress?.logEntries || []"
      :error="buildError"
      :disconnected="buildDisconnected"
      @cancel="cancelBuild"
      @retry="retryBuild"
    />
  </div>

  <!-- Ready state: interactive graph -->
  <div v-else class="h-full flex relative">
    <div class="flex-1 relative">
      <div class="absolute top-3 left-3 right-3 z-10 flex gap-2">
        <div
          class="flex-1 flex items-center gap-2 px-3 py-2 rounded-lg border"
          :style="{ backgroundColor: 'var(--surface-raised)', borderColor: 'var(--border)', boxShadow: 'var(--shadow-sm)' }"
        >
          <Search :size="14" :style="{ color: 'var(--text-tertiary)' }" />
          <input
            v-model="searchQuery"
            placeholder="Search entities..."
            class="flex-1 text-sm bg-transparent outline-none"
            :style="{ color: 'var(--text-primary)' }"
          />
        </div>
        <div class="flex gap-1 items-center">
          <button
            v-for="type in entityTypes"
            :key="type"
            class="px-2.5 py-1.5 rounded-md text-xs font-medium text-white transition-opacity"
            :style="{ backgroundColor: NODE_COLORS[type] || '#6366f1', opacity: activeFilters.length && !activeFilters.includes(type) ? 0.4 : 1 }"
            @click="toggleFilter(type)"
          >{{ type }}</button>
        </div>
      </div>

      <div ref="svgContainer" class="w-full h-full min-h-[500px]" />

      <div class="absolute bottom-3 left-3 flex gap-1">
        <button class="w-8 h-8 rounded-md border flex items-center justify-center" :style="{ backgroundColor: 'var(--surface-raised)', borderColor: 'var(--border)', boxShadow: 'var(--shadow-sm)' }"><Plus :size="14" /></button>
        <button class="w-8 h-8 rounded-md border flex items-center justify-center" :style="{ backgroundColor: 'var(--surface-raised)', borderColor: 'var(--border)', boxShadow: 'var(--shadow-sm)' }"><Minus :size="14" /></button>
        <button class="w-8 h-8 rounded-md border flex items-center justify-center" :style="{ backgroundColor: 'var(--surface-raised)', borderColor: 'var(--border)', boxShadow: 'var(--shadow-sm)' }"><RotateCcw :size="12" /></button>
      </div>
      <div class="absolute bottom-3 right-3">
        <button
          class="px-3 py-1.5 rounded-md border text-xs"
          :style="{ backgroundColor: 'var(--surface-raised)', borderColor: 'var(--border)', color: 'var(--text-secondary)', boxShadow: 'var(--shadow-sm)' }"
          @click="showRebuildModal = true"
        >Rebuild Graph</button>
      </div>
    </div>

    <div
      v-if="selectedNode"
      class="w-[260px] border-l shrink-0 overflow-y-auto"
      :style="{ backgroundColor: 'var(--surface-raised)', borderColor: 'var(--border)', transition: 'width var(--duration-slow) var(--ease-out)' }"
    >
      <div class="p-4 border-b" :style="{ borderColor: 'var(--border)' }">
        <div class="flex items-center justify-between">
          <div class="flex items-center gap-2">
            <div class="w-2.5 h-2.5 rounded-full" :style="{ backgroundColor: NODE_COLORS[selectedNode.type] || '#6366f1' }" />
            <span class="text-xs uppercase tracking-wider" :style="{ color: 'var(--text-secondary)', fontFamily: 'var(--font-mono)' }">{{ selectedNode.type }}</span>
          </div>
          <button class="opacity-50 hover:opacity-100 text-xs" @click="closeDetail">✕</button>
        </div>
        <h3 class="text-base font-semibold mt-2" :style="{ fontFamily: 'var(--font-display)', color: 'var(--text-primary)' }">{{ selectedNode.id }}</h3>
      </div>
      <div class="p-4">
        <div v-if="selectedNode.description" class="mb-4">
          <p class="text-xs uppercase tracking-wider mb-1" :style="{ color: 'var(--text-secondary)', fontFamily: 'var(--font-mono)' }">Description</p>
          <p class="text-sm leading-relaxed" :style="{ color: 'var(--text-secondary)' }">{{ selectedNode.description }}</p>
        </div>
        <div v-if="selectedNode.connections?.length">
          <p class="text-xs uppercase tracking-wider mb-2" :style="{ color: 'var(--text-secondary)', fontFamily: 'var(--font-mono)' }">Connected To</p>
          <div class="space-y-1.5">
            <div
              v-for="conn in selectedNode.connections"
              :key="conn.node"
              class="flex items-center gap-2 px-2 py-1.5 rounded-md cursor-pointer"
              :style="{ backgroundColor: 'var(--surface-sunken)' }"
            >
              <div class="w-2 h-2 rounded-full" :style="{ backgroundColor: NODE_COLORS[conn.type] || '#6366f1' }" />
              <span class="text-sm flex-1" :style="{ color: 'var(--text-primary)' }">{{ conn.node }}</span>
              <span class="text-xs" :style="{ color: 'var(--text-tertiary)', fontFamily: 'var(--font-mono)' }">{{ conn.label }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <ConfirmModal
      v-if="showRebuildModal"
      title="Rebuild Knowledge Graph?"
      message="This will build a new knowledge graph. Existing simulations keep their original graph data. New simulations will use the rebuilt graph."
      confirmLabel="Rebuild"
      variant="warning"
      @confirm="confirmRebuild"
      @cancel="showRebuildModal = false"
    />
  </div>
</template>
