import { createRouter, createWebHashHistory } from 'vue-router'
import Catalogo from './views/Catalogo.vue'

// Hash history: obrigatório sob file:// no build (o history normal quebra; guia §7).
export const router = createRouter({
  history: createWebHashHistory(),
  routes: [
    { path: '/', name: 'catalogo', component: Catalogo },
  ],
})
