// Estado de la sesión: usuario, rol y sede activa (pantallas P01 a P04).
import { defineStore } from 'pinia'
import { api } from '../services/api'

export const useSesion = defineStore('sesion', {
  state: () => ({
    usuario: null,
    sedes: [],
    sedeActivaId: null
  }),
  getters: {
    autenticado: (estado) => estado.usuario !== null,
    esAdministradoraDelCentro: (estado) => estado.usuario?.rol === 'ADMIN_CENTRO',
    necesitaElegirSede: (estado) => estado.sedes.length > 1 && estado.sedeActivaId === null
  },
  actions: {
    async cargarSedes () {
      const { data } = await api.get('/sesion/sedes/')
      this.sedes = data.sedes
      if (!data.requiere_eleccion && data.sedes.length === 1) {
        this.sedeActivaId = data.sedes[0].id
      }
    },
    elegirSede (sedeId) {
      this.sedeActivaId = sedeId
    },
    cerrarSesion () {
      this.$reset()
    }
  }
})
