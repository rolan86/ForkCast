<script setup>
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { createProject } from '@/api/projects.js'
import { apiGet } from '@/api/client.js'
import StepIndicator from '@/components/StepIndicator.vue'
import { Upload, X, FileText, Loader2 } from 'lucide-vue-next'

const router = useRouter()

const currentStep = ref(0)
const submitting = ref(false)
const submitError = ref('')

const name = ref('')
const domain = ref('')
const requirement = ref('')
const files = ref([])
const domains = ref([])

const errors = ref({})

;(async () => {
  try {
    const resp = await apiGet('/api/domains')
    domains.value = resp.data || []
    if (domains.value.length) domain.value = domains.value[0].name || domains.value[0]
  } catch { /* ignore */ }
})()

const steps = computed(() => [
  { label: 'Define', status: currentStep.value > 0 ? 'done' : currentStep.value === 0 ? 'active' : 'pending' },
  { label: 'Upload', status: currentStep.value > 1 ? 'done' : currentStep.value === 1 ? 'active' : 'pending' },
  { label: 'Review', status: currentStep.value === 2 ? 'active' : 'pending' },
])

function validateStep0() {
  errors.value = {}
  if (!name.value.trim()) errors.value.name = 'Project name is required'
  if (!domain.value) errors.value.domain = 'Domain is required'
  if (!requirement.value.trim() || requirement.value.trim().length < 10) {
    errors.value.requirement = 'Prediction question must be at least 10 characters'
  }
  return Object.keys(errors.value).length === 0
}

function validateStep1() {
  errors.value = {}
  if (!files.value.length) errors.value.files = 'At least one file is required'
  return Object.keys(errors.value).length === 0
}

function next() {
  if (currentStep.value === 0 && !validateStep0()) return
  if (currentStep.value === 1 && !validateStep1()) return
  currentStep.value++
}

function back() {
  if (currentStep.value > 0) currentStep.value--
}

const ALLOWED_TYPES = ['application/pdf', 'text/markdown', 'text/plain']
const ALLOWED_EXTS = ['.pdf', '.md', '.txt']
const MAX_SIZE = 10 * 1024 * 1024

function handleDrop(e) {
  const dropped = Array.from(e.dataTransfer?.files || [])
  addFiles(dropped)
}

function handleFileInput(e) {
  addFiles(Array.from(e.target.files || []))
  e.target.value = ''
}

function addFiles(newFiles) {
  errors.value = {}
  for (const f of newFiles) {
    const ext = '.' + f.name.split('.').pop().toLowerCase()
    if (!ALLOWED_EXTS.includes(ext) && !ALLOWED_TYPES.includes(f.type)) {
      errors.value.files = `Unsupported file type: ${ext}. Use PDF, Markdown, or Text files.`
      return
    }
    if (f.size > MAX_SIZE) {
      errors.value.files = `${f.name} exceeds 10MB limit.`
      return
    }
    files.value.push(f)
  }
}

function removeFile(index) {
  files.value.splice(index, 1)
}

function formatSize(bytes) {
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB'
}

async function submit() {
  submitting.value = true
  submitError.value = ''
  try {
    const project = await createProject({
      name: name.value.trim(),
      domain: domain.value,
      requirement: requirement.value.trim(),
      files: files.value,
    })
    router.push(`/projects/${project.id}/overview`)
  } catch (e) {
    submitError.value = e.message || 'Failed to create project'
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <div class="p-10 max-w-2xl mx-auto">
    <h1 class="text-2xl font-bold mb-6" :style="{ fontFamily: 'var(--font-display)', color: 'var(--text-primary)' }">New Project</h1>

    <div class="mb-8">
      <StepIndicator :steps="steps" mode="wizard" />
    </div>

    <!-- Step 0: Define -->
    <div v-if="currentStep === 0" class="space-y-5">
      <div>
        <label class="block text-sm font-medium mb-1.5" :style="{ color: 'var(--text-primary)' }">Project Name</label>
        <input
          v-model="name"
          class="w-full px-3 py-2 rounded-md border text-sm outline-none transition-colors"
          :style="{ borderColor: errors.name ? 'var(--danger)' : 'var(--border)', backgroundColor: 'var(--surface)', color: 'var(--text-primary)' }"
          placeholder="e.g., AI Regulation Forecast"
          @blur="errors.name && validateStep0()"
        />
        <p v-if="errors.name" class="text-xs mt-1" :style="{ color: 'var(--danger)' }">{{ errors.name }}</p>
      </div>
      <div>
        <label class="block text-sm font-medium mb-1.5" :style="{ color: 'var(--text-primary)' }">Domain</label>
        <select
          v-model="domain"
          class="w-full px-3 py-2 rounded-md border text-sm outline-none"
          :style="{ borderColor: errors.domain ? 'var(--danger)' : 'var(--border)', backgroundColor: 'var(--surface)', color: 'var(--text-primary)' }"
        >
          <option v-for="d in domains" :key="d.name || d" :value="d.name || d">{{ d.name || d }}</option>
        </select>
        <p v-if="errors.domain" class="text-xs mt-1" :style="{ color: 'var(--danger)' }">{{ errors.domain }}</p>
      </div>
      <div>
        <label class="block text-sm font-medium mb-1.5" :style="{ color: 'var(--text-primary)' }">Prediction Question</label>
        <textarea
          v-model="requirement"
          rows="3"
          class="w-full px-3 py-2 rounded-md border text-sm outline-none resize-none"
          :style="{ borderColor: errors.requirement ? 'var(--danger)' : 'var(--border)', backgroundColor: 'var(--surface)', color: 'var(--text-primary)' }"
          placeholder="What will happen when the EU AI Act takes effect?"
          @blur="errors.requirement && validateStep0()"
        />
        <p v-if="errors.requirement" class="text-xs mt-1" :style="{ color: 'var(--danger)' }">{{ errors.requirement }}</p>
      </div>
    </div>

    <!-- Step 1: Upload -->
    <div v-if="currentStep === 1" class="space-y-4">
      <div
        class="border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition-colors"
        :style="{ borderColor: errors.files ? 'var(--danger)' : 'var(--border)' }"
        @drop.prevent="handleDrop"
        @dragover.prevent
        @dragenter.prevent="$el.style.borderColor = 'var(--accent)'; $el.style.backgroundColor = 'var(--accent-surface)'"
        @dragleave.prevent="$el.style.borderColor = 'var(--border)'; $el.style.backgroundColor = ''"
        @click="$refs.fileInput.click()"
      >
        <Upload :size="32" :style="{ color: 'var(--text-tertiary)', margin: '0 auto' }" />
        <p class="mt-3 text-sm" :style="{ color: 'var(--text-secondary)' }">Drop files here or click to browse</p>
        <p class="mt-1 text-xs" :style="{ color: 'var(--text-tertiary)' }">PDF, Markdown, Text — Max 10MB each</p>
        <input ref="fileInput" type="file" multiple accept=".pdf,.md,.txt" class="hidden" @change="handleFileInput" />
      </div>
      <p v-if="errors.files" class="text-xs" :style="{ color: 'var(--danger)' }">{{ errors.files }}</p>

      <div v-for="(f, i) in files" :key="i" class="flex items-center gap-3 p-3 rounded-lg border" :style="{ borderColor: 'var(--border)', backgroundColor: 'var(--surface-raised)' }">
        <FileText :size="16" :style="{ color: 'var(--text-tertiary)' }" />
        <span class="flex-1 text-sm truncate" :style="{ color: 'var(--text-primary)' }">{{ f.name }}</span>
        <span class="text-xs" :style="{ color: 'var(--text-tertiary)', fontFamily: 'var(--font-mono)' }">{{ formatSize(f.size) }}</span>
        <button @click="removeFile(i)" class="hover:opacity-100 opacity-50 transition-opacity">
          <X :size="14" :style="{ color: 'var(--danger)' }" />
        </button>
      </div>
    </div>

    <!-- Step 2: Review -->
    <div v-if="currentStep === 2" class="space-y-4">
      <div class="rounded-xl border p-5" :style="{ borderColor: 'var(--border)', backgroundColor: 'var(--surface-raised)' }">
        <div class="space-y-3">
          <div><span class="text-xs uppercase tracking-wider" :style="{ color: 'var(--text-secondary)', fontFamily: 'var(--font-mono)' }">Name</span><p class="text-sm mt-0.5" :style="{ color: 'var(--text-primary)' }">{{ name }}</p></div>
          <div><span class="text-xs uppercase tracking-wider" :style="{ color: 'var(--text-secondary)', fontFamily: 'var(--font-mono)' }">Domain</span><p class="text-sm mt-0.5" :style="{ color: 'var(--text-primary)' }">{{ domain }}</p></div>
          <div><span class="text-xs uppercase tracking-wider" :style="{ color: 'var(--text-secondary)', fontFamily: 'var(--font-mono)' }">Prediction Question</span><p class="text-sm mt-0.5" :style="{ color: 'var(--text-primary)' }">{{ requirement }}</p></div>
          <div><span class="text-xs uppercase tracking-wider" :style="{ color: 'var(--text-secondary)', fontFamily: 'var(--font-mono)' }">Files ({{ files.length }})</span>
            <div class="mt-1 space-y-1">
              <p v-for="f in files" :key="f.name" class="text-sm" :style="{ color: 'var(--text-primary)' }">{{ f.name }} <span :style="{ color: 'var(--text-tertiary)', fontFamily: 'var(--font-mono)' }">({{ formatSize(f.size) }})</span></p>
            </div>
          </div>
        </div>
      </div>
      <p v-if="submitError" class="text-sm" :style="{ color: 'var(--danger)' }">{{ submitError }}</p>
    </div>

    <!-- Navigation -->
    <div class="flex justify-between mt-8">
      <button
        v-if="currentStep > 0"
        class="px-4 py-2 rounded-lg text-sm border"
        :style="{ borderColor: 'var(--border)', color: 'var(--text-secondary)' }"
        @click="back"
      >Back</button>
      <div v-else />
      <button
        v-if="currentStep < 2"
        class="px-6 py-2 rounded-lg text-sm font-medium text-white"
        :style="{ backgroundColor: 'var(--accent)' }"
        @click="next"
      >Continue</button>
      <button
        v-else
        class="px-6 py-2 rounded-lg text-sm font-medium text-white flex items-center gap-2"
        :style="{ backgroundColor: 'var(--accent)', opacity: submitting ? 0.7 : 1 }"
        :disabled="submitting"
        @click="submit"
      >
        <Loader2 v-if="submitting" :size="14" class="animate-spin" />
        {{ submitting ? 'Creating...' : 'Create Project' }}
      </button>
    </div>
  </div>
</template>
