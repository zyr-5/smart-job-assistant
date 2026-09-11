import { createRouter, createWebHistory } from 'vue-router'
import Home from '../views/Home.vue'
import Match from '../views/Match.vue'
import Interview from '../views/Interview.vue'

const routes = [
  { path: '/', name: 'home', component: Home },
  { path: '/match', name: 'match', component: Match },
  { path: '/interview', name: 'interview', component: Interview },
]

export default createRouter({
  history: createWebHistory(),
  routes,
})
