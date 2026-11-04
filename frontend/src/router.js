// Rutas del cliente, derivadas del mapa de navegación de la Práctica N.° 7.
import { createRouter, createWebHistory } from 'vue-router'
import { useSesion } from './stores/sesion'

const rutas = [
  { path: '/', redirect: '/panel' },
  { path: '/ingresar', name: 'login', component: () => import('./views/LoginView.vue'), meta: { publica: true } },
  { path: '/elegir-sede', name: 'elegir-sede', component: () => import('./views/ElegirSedeView.vue') },
  { path: '/panel', name: 'panel', component: () => import('./views/PanelDelDiaView.vue') },
  { path: '/agenda', name: 'agenda', component: () => import('./views/AgendaView.vue') },
  { path: '/pacientes', name: 'pacientes', component: () => import('./views/PacientesView.vue') },
  { path: '/:rutaNoEncontrada(.*)*', name: 'error', component: () => import('./views/ErrorView.vue'), meta: { publica: true } }
]

export const router = createRouter({ history: createWebHistory(), routes: rutas })

router.beforeEach((destino) => {
  const sesion = useSesion()
  if (!destino.meta.publica && !sesion.autenticado) return { name: 'login' }
  // Con sesión abierta, el formulario de ingreso ya no tiene sentido.
  if (destino.name === 'login' && sesion.autenticado) return { name: 'panel' }
  if (sesion.autenticado && sesion.necesitaElegirSede && destino.name !== 'elegir-sede') {
    return { name: 'elegir-sede' }
  }
  return true
})
