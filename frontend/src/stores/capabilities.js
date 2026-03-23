import { defineStore } from 'pinia'
import { getCapabilities } from '@/api/capabilities.js'

export const useCapabilitiesStore = defineStore('capabilities', {
  state: () => ({
    engines: {},
    models: [],
    loaded: false,
  }),

  getters: {
    isOasisAvailable(state) {
      return state.engines?.oasis?.available === true
    },
    modelOptions(state) {
      return state.models.map(m => ({ value: m.id, label: m.label }))
    },
  },

  actions: {
    async fetch() {
      if (this.loaded) return
      try {
        const data = await getCapabilities()
        this.engines = data.engines
        this.models = data.models
        this.loaded = true
      } catch (e) {
        console.warn('Failed to fetch capabilities:', e)
      }
    },
  },
})
