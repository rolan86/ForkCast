import { defineStore } from 'pinia'
import * as projectsApi from '@/api/projects.js'
import * as graphsApi from '@/api/graphs.js'
import * as simulationsApi from '@/api/simulations.js'

export const useProjectStore = defineStore('project', {
  state: () => ({
    projects: [],
    currentProject: null,
    currentGraph: null,
    simulations: [],
    currentSimulation: null,
    graphBuildProgress: null,
    simPrepareProgress: null,
    simRunProgress: null,
    liveFeedActions: [],
    reportProgress: null,
  }),

  getters: {
    projectSimulations(state) {
      if (!state.currentProject) return []
      return state.simulations.filter(s => s.project_id === state.currentProject.id)
    },
  },

  actions: {
    async fetchProjects() {
      this.projects = await projectsApi.listProjects()
    },
    async fetchProject(id) {
      this.currentProject = await projectsApi.getProject(id)
    },
    async fetchGraph(projectId) {
      try {
        this.currentGraph = await graphsApi.getGraph(projectId)
      } catch (e) {
        if (e.status === 404) this.currentGraph = null
        else throw e
      }
    },
    async fetchSimulations() {
      this.simulations = await simulationsApi.listSimulations()
    },
    async fetchSimulation(id) {
      this.currentSimulation = await simulationsApi.getSimulation(id)
    },

    updateGraphBuildProgress(data) {
      if (!this.graphBuildProgress) {
        this.graphBuildProgress = { stage: '', current: null, total: null, logEntries: [] }
      }
      this.graphBuildProgress.stage = data.stage
      if (data.current != null) this.graphBuildProgress.current = data.current
      if (data.total != null) this.graphBuildProgress.total = data.total
      this.graphBuildProgress.logEntries.push({
        message: data.stage + (data.current ? ` (${data.current}/${data.total})` : ''),
        type: 'progress',
      })
    },
    resetGraphBuildProgress() {
      this.graphBuildProgress = null
    },

    updateSimPrepareProgress(data) {
      if (!this.simPrepareProgress) {
        this.simPrepareProgress = { stage: '', current: null, total: null, logEntries: [] }
      }
      this.simPrepareProgress.stage = data.stage
      if (data.current != null) this.simPrepareProgress.current = data.current
      if (data.total != null) this.simPrepareProgress.total = data.total
      this.simPrepareProgress.logEntries.push({
        message: data.stage + (data.current ? ` (${data.current}/${data.total})` : ''),
        type: 'progress',
      })
    },
    resetSimPrepareProgress() {
      this.simPrepareProgress = null
    },

    updateSimRunProgress(data) {
      if (!this.simRunProgress) {
        this.simRunProgress = { stage: '', currentRound: null, totalRounds: null }
      }
      if (data.stage === 'round') {
        this.simRunProgress.currentRound = data.current
        this.simRunProgress.totalRounds = data.total
      }
      if (data.stage === 'running') {
        this.simRunProgress.totalRounds = data.total_rounds
      }
      this.simRunProgress.stage = data.stage
    },
    addLiveFeedAction(action) {
      this.liveFeedActions.unshift(action)
      if (this.liveFeedActions.length > 200) {
        this.liveFeedActions.length = 200
      }
    },
    resetSimRunProgress() {
      this.simRunProgress = null
      this.liveFeedActions = []
    },
  },
})
