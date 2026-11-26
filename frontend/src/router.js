// Rutas del cliente, derivadas del mapa de navegación de la Práctica N.° 7.
import { createRouter, createWebHistory } from 'vue-router'
import { useSesion } from './stores/sesion'

// Pantallas del personal de un centro: el administrador de plataforma no
// pertenece a ningún centro y no tiene nada que hacer en ellas.
const CENTRO = ['ADMIN_CENTRO', 'PODOLOGA']

// En `meta`: `roles` decide quién entra; `menu` es el texto del enlace en la
// barra superior (solo las rutas que lo tienen salen en ella) y `seccion`
// indica qué enlace del menú queda marcado en una pantalla que no está en él.
const rutas = [
  { path: '/', redirect: '/panel' },
  { path: '/ingresar', name: 'login', component: () => import('./views/LoginView.vue'), meta: { publica: true } },
  { path: '/elegir-sede', name: 'elegir-sede', component: () => import('./views/ElegirSedeView.vue'), meta: { roles: CENTRO } },
  { path: '/panel', name: 'panel', component: () => import('./views/PanelDelDiaView.vue'), meta: { roles: CENTRO, menu: 'Panel del día' } },
  { path: '/agenda', name: 'agenda', component: () => import('./views/AgendaView.vue'), meta: { roles: CENTRO, menu: 'Agenda' } },
  { path: '/citas/:citaId/atencion', name: 'registrar-atencion', component: () => import('./views/RegistrarAtencionView.vue'), props: true, meta: { roles: CENTRO, seccion: 'agenda' } },
  { path: '/pacientes', name: 'pacientes', component: () => import('./views/PacientesView.vue'), meta: { roles: CENTRO, menu: 'Pacientes' } },
  { path: '/pacientes/nuevo', name: 'nuevo-paciente', component: () => import('./views/NuevoPacienteView.vue'), meta: { roles: CENTRO, seccion: 'pacientes' } },
  { path: '/pacientes/:pacienteId', name: 'ficha-paciente', component: () => import('./views/FichaPacienteView.vue'), props: true, meta: { roles: CENTRO, seccion: 'pacientes' } },
  { path: '/inventario', name: 'inventario', component: () => import('./views/InventarioView.vue'), meta: { roles: CENTRO, menu: 'Inventario' } },
  { path: '/registro-diario', name: 'registro-diario', component: () => import('./views/RegistroDiarioView.vue'), meta: { roles: CENTRO, menu: 'Registro diario' } },
  // Administración del centro: solo la administradora (Práctica N.° 7, Tabla 1).
  { path: '/usuarios', name: 'usuarios', component: () => import('./views/UsuariosView.vue'), meta: { roles: ['ADMIN_CENTRO'], menu: 'Usuarios' } },
  { path: '/sedes', name: 'sedes', component: () => import('./views/SedesView.vue'), meta: { roles: ['ADMIN_CENTRO'], menu: 'Sedes' } },
  { path: '/servicios', name: 'servicios', component: () => import('./views/ServiciosView.vue'), meta: { roles: ['ADMIN_CENTRO'], menu: 'Servicios' } },
  // Plataforma (P19 y P29): solo el administrador de plataforma.
  { path: '/centros', name: 'centros', component: () => import('./views/CentrosView.vue'), meta: { roles: ['ADMIN_PLATAFORMA'], menu: 'Centros clientes' } },
  // P21: la misma plantilla para la falta de permiso y para la ruta inexistente.
  { path: '/perfil', name: 'perfil', component: () => import('./views/PerfilView.vue') },
  // P02 (alta): verificación en dos pasos, obligatoria para los roles administrativos.
  { path: '/segundo-factor', name: 'segundo-factor', component: () => import('./views/SegundoFactorView.vue') },
  { path: '/sin-permiso', name: 'sin-permiso', component: () => import('./views/ErrorView.vue'), props: { codigo: 403 } },
  { path: '/:rutaNoEncontrada(.*)*', name: 'error', component: () => import('./views/ErrorView.vue'), props: { codigo: 404 }, meta: { publica: true } }
]

// Secciones de la barra superior, en el orden en que se declaran arriba.
export const SECCIONES = rutas.filter((ruta) => ruta.meta?.menu)

export const router = createRouter({ history: createWebHistory(), routes: rutas })

router.beforeEach((destino) => {
  const sesion = useSesion()
  if (!destino.meta.publica && !sesion.autenticado) return { name: 'login' }
  // Con sesión abierta, el formulario de ingreso ya no tiene sentido.
  if (destino.name === 'login' && sesion.autenticado) return { name: 'panel' }
  // El inicio del administrador de plataforma es la lista de centros, no el
  // panel del día de un centro.
  if (destino.name === 'panel' && sesion.esAdministradoraDePlataforma) return { name: 'centros' }
  // Con contraseña temporal el servidor solo deja cambiarla: se lleva al
  // usuario a P20 antes que a cualquier otra pantalla, incluida la de sede.
  if (sesion.usuario?.debe_cambiar_contrasena && destino.name !== 'perfil') {
    return { name: 'perfil' }
  }
  // RF18: un rol administrativo sin segundo factor solo puede darlo de alta;
  // el servidor rechaza todo lo demás con «segundo-factor-pendiente».
  if (sesion.usuario?.debe_activar_segundo_factor && !sesion.usuario?.debe_cambiar_contrasena &&
      destino.name !== 'segundo-factor') {
    return { name: 'segundo-factor' }
  }
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
