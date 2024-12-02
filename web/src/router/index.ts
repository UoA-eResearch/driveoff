import { createRouter, createWebHistory } from 'vue-router'
import HomeView from '../views/HomeView.vue'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/',
      name: 'home',
      component: HomeView
    },
    {
      path: '/summary',
      name: 'summary',
      component: () => import('../views/SummaryView.vue')
    },
    {
      path: "/check-details",
      name: 'check-details',
      component: () => import("../views/CheckDetailsView.vue")
    },
    {
      path: "/update-details",
      name: 'update-details',
      component: () => import("../views/UpdateDetailsView.vue")
    },
    {
      path: "/data-classification",
      name: "data-classification",
      component: () => import("../views/DataClassificationView.vue")
    },
    {
      path: "/retention-period",
      name: "retention-period",
      component: () => import("../views/RetentionPeriodView.vue")
    },
    {
      path: "/custom-retention-period",
      name: "custom-retention-period",
      component: () => import("../views/CustomRetentionPeriodView.vue")
    },
    {
      path: "/confirm",
      name: "confirm",
      component: () => import("../views/ConfirmArchiveView.vue")
    },
    {
      path: "/finish",
      name: "finish",
      component: () => import("../views/FinishView.vue")
    },
    {
      path: "/unable-to-archive",
      name: "unable-to-archive",
      component: () => import("../views/UnableToArchiveView.vue")
    }
  ]
})

export default router
