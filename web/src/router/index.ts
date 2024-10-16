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
      path: '/about',
      name: 'about',
      // route level code-splitting
      // this generates a separate chunk (About.[hash].js) for this route
      // which is lazy-loaded when the route is visited.
      component: () => import('../views/AboutView.vue')
    },
    {
      path: '/summary',
      name: 'summary',
      component: () => import('../views/SummaryView.vue')
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
      path: "/confirm",
      name: "confirm",
      component: () => import("../views/ConfirmArchiveView.vue")
    },
    {
      path: "/finish",
      name: "finish",
      component: () => import("../views/FinishView.vue")
    }
  ]
})

export default router
