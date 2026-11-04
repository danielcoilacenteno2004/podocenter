// Estado de la sesión: usuario, rol y sede activa (pantallas P01 a P04).
import { defineStore } from 'pinia'
import { api } from '../services/api'

const SEDE_GUARDADA = 'podocenter.sede'

export const useSesion = defineStore('sesion', {
  state: () => ({
    usuario: null,
    sedes: [],
    sedeActivaId: null,
    restaurada: false
  }),
  getters: {
    autenticado: (estado) => estado.usuario !== null,
    esAdministradoraDelCentro: (estado) => estado.usuario?.rol === 'ADMIN_CENTRO',
    esAdministradoraDePlataforma: (estado) => estado.usuario?.rol === 'ADMIN_PLATAFORMA',
    necesitaElegirSede: (estado) => estado.sedes.length > 1 && estado.sedeActivaId === null,
    sedeActiva: (estado) => estado.sedes.find((s) => s.id === estado.sedeActivaId) ?? null
  },
  actions: {
    // Pide el estado al servidor; de paso deja la cookie CSRF en el navegador.
    async restaurar () {
      try {
        const { data } = await api.get('/sesion/actual/')
        if (data.autenticado) {
          this.usuario = data.usuario
          await this.cargarSedes()
        }
      } catch {
        this.usuario = null
      } finally {
        this.restaurada = true
      }
    },

    async iniciarSesion (correo, contrasena) {
      const { data } = await api.post('/sesion/ingresar/', { correo, contrasena })
      this.usuario = data.usuario
      await this.cargarSedes()
    },

    async cargarSedes () {
      if (this.usuario?.rol === 'ADMIN_PLATAFORMA') {
        this.sedes = []
        return
      }
      const { data } = await api.get('/sesion/sedes/')
      this.sedes = data.sedes
      const recordada = Number(localStorage.getItem(SEDE_GUARDADA))
      if (recordada && data.sedes.some((s) => s.id === recordada)) {
        this.sedeActivaId = recordada
      } else if (!data.requiere_eleccion && data.sedes.length === 1) {
        this.sedeActivaId = data.sedes[0].id
      }
    },

    elegirSede (sedeId) {
      this.sedeActivaId = sedeId
      try {
        localStorage.setItem(SEDE_GUARDADA, String(sedeId))
      } catch {
        // Navegación privada o almacenamiento bloqueado: la sede vale solo
        // para esta sesión y no es motivo para interrumpir al usuario.
      }
    },

    async cerrarSesion () {
      try {
        await api.post('/sesion/salir/')
      } finally {
        try { localStorage.removeItem(SEDE_GUARDADA) } catch { /* ver elegirSede */ }
        this.$reset()
        this.restaurada = true
      }
    }
  }
})
