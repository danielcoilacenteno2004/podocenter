// Rutas del cliente, derivadas del mapa de navegación de la Práctica N.° 7.
import { createRouter, createWebHistory } from 'vue-router'
import { useSesion } from './stores/sesion'

// Pantallas del personal de un centro: el administrador de plataforma no
// pertenece a ningún centro y no tiene nada que hacer en ellas.
const CENTRO = ['ADMIN_CENTRO', 'PODOLOGA']

const rutas = [
  { path: '/', redirect: '/panel' },
  { path: '/ingresar', name: 'login', component: () => import('./views/LoginView.vue'), meta: { publica: true } },
  { path: '/elegir-sede', name: 'elegir-sede', component: () => import('./views/ElegirSedeView.vue'), meta: { roles: CENTRO } },
  { path: '/panel', name: 'panel', component: () => import('./views/PanelDelDiaView.vue'), meta: { roles: CENTRO } },
  { path: '/agenda', name: 'agenda', component: () => import('./views/AgendaView.vue'), meta: { roles: CENTRO } },
  { path: '/citas/:citaId/atencion', name: 'registrar-atencion', component: () => import('./views/RegistrarAtencionView.vue'), props: true, meta: { roles: CENTRO } },
  { path: '/pacientes', name: 'pacientes', component: () => import('./views/PacientesView.vue'), meta: { roles: CENTRO } },
  { path: '/pacientes/nuevo', name: 'nuevo-paciente', component: () => import('./views/NuevoPacienteView.vue'), meta: { roles: CENTRO } },
  { path: '/pacientes/:pacienteId', name: 'ficha-paciente', component: () => import('./views/FichaPacienteView.vue'), props: true, meta: { roles: CENTRO } },
  // Administración del centro: solo la administradora (Práctica N.° 7, Tabla 1).
  { path: '/usuarios', name: 'usuarios', component: () => import('./views/UsuariosView.vue'), meta: { roles: ['ADMIN_CENTRO'] } },
  { path: '/sedes', name: 'sedes', component: () => import('./views/SedesView.vue'), meta: { roles: ['ADMIN_CENTRO'] } },
  { path: '/servicios', name: 'servicios', component: () => import('./views/ServiciosView.vue'), meta: { roles: ['ADMIN_CENTRO'] } },
  // Plataforma (P19 y P29): solo el administrador de plataforma.
  { path: '/centros', name: 'centros', component: () => import('./views/CentrosView.vue'), meta: { roles: ['ADMIN_PLATAFORMA'] } },
  // P21: la misma plantilla para la falta de permiso y para la ruta inexistente.
  { path: '/perfil', name: 'perfil', component: () => import('./views/PerfilView.vue') },
  { path: '/sin-permiso', name: 'sin-permiso', component: () => import('./views/ErrorView.vue'), props: { codigo: 403 } },
  { path: '/:rutaNoEncontrada(.*)*', name: 'error', component: () => import('./views/ErrorView.vue'), props: { codigo: 404 }, meta: { publica: true } }
]

export const router = createRouter({ history: createWebHistory(), routes: rutas })

router.beforeEach((destino) => {
  const sesion = useSesion()
  if (!destino.meta.publica && !sesion.autenticado) return { name: 'login' }
  // Con sesión abierta, el formulario de ingreso ya no tiene sentido.
  if (destino.name === 'login' && sesion.autenticado) return { name: 'panel' }
  // El inicio del administrador de plataforma es la lista de centros, no el
  // panel del día de un centro.
  if (destino.name === 'panel' && sesion.esAdministradoraDePlataforma) return { name: 'centros' }
  if (sesion.autenticado && sesion.necesitaElegirSede && destino.name !== 'elegir-sede') {
    return { name: 'elegir-sede' }
  }
  // El menú ya no muestra lo que el rol no permite; esto cubre a quien
  // escribe la dirección a mano: ve P21 en lugar de volver al panel sin
  // saber por qué. El servidor responde 403 de todos modos.
  if (destino.meta.roles && !destino.meta.roles.includes(sesion.usuario?.rol)) {
    return { name: 'sin-permiso', replace: true }
  }
  return true
})
