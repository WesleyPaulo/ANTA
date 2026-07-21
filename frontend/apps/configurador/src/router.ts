import { createRouter, createWebHashHistory } from 'vue-router'
import Modelo from './views/Modelo.vue'
import Audio from './views/Audio.vue'
import Ajustes from './views/Ajustes.vue'
import Instalar from './views/Instalar.vue'

// Hash history: obrigatório sob file:// no build (o history normal quebra; guia §7).
export const STEPS = [
  { key: 'modelo', label: 'Modelo', path: '/modelo' },
  { key: 'audio', label: 'Áudio', path: '/audio' },
  { key: 'ajustes', label: 'Ajustes', path: '/ajustes' },
  { key: 'instalar', label: 'Instalar', path: '/instalar' },
]

export const router = createRouter({
  history: createWebHashHistory(),
  routes: [
    { path: '/', redirect: '/modelo' },
    { path: '/modelo', name: 'modelo', component: Modelo },
    { path: '/audio', name: 'audio', component: Audio },
    { path: '/ajustes', name: 'ajustes', component: Ajustes },
    { path: '/instalar', name: 'instalar', component: Instalar },
  ],
})
