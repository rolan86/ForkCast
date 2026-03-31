import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  { path: '/', redirect: '/projects' },
  {
    path: '/projects',
    name: 'projects',
    component: () => import('@/views/ProjectListView.vue'),
  },
  {
    path: '/projects/new',
    name: 'project-new',
    component: () => import('@/views/ProjectWizard.vue'),
  },
  {
    path: '/projects/:id',
    component: () => import('@/views/ProjectLayout.vue'),
    children: [
      { path: '', redirect: { name: 'project-overview' } },
      { path: 'overview', name: 'project-overview', component: () => import('@/views/OverviewTab.vue') },
      { path: 'graph', name: 'project-graph', component: () => import('@/views/GraphTab.vue') },
      { path: 'simulations', name: 'project-simulations', component: () => import('@/views/SimulationTab.vue') },
      { path: 'reports', name: 'project-reports', component: () => import('@/views/ReportTab.vue') },
      {
        path: 'interact',
        name: 'project-interact',
        component: () => import('@/views/InteractTab.vue'),
      },
    ],
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

export default router
