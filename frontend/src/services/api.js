// Cliente HTTP único de la aplicación.
// Centralizar aquí la base, la sede activa y el tratamiento de errores evita
// que cada pantalla repita esa lógica (Práctica N.° 7, sección 3.3).
import axios from 'axios'
import { useSesion } from '../stores/sesion'

export const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL ?? '/api/v1',
  withCredentials: true,
  xsrfCookieName: 'csrftoken',
  xsrfHeaderName: 'X-CSRFToken'
})

api.interceptors.request.use((config) => {
  const sesion = useSesion()
  if (sesion.sedeActivaId) {
    config.headers['X-Sede'] = sesion.sedeActivaId
  }
  return config
})

// En un error de validación (400) el servidor devuelve `detail` como un
// objeto { campo: [mensajes] }; sin aplanarlo, la usuaria leería
// «[object Object]». Se juntan los mensajes y se conservan por campo.
function textoDelDetalle (detalle) {
  if (typeof detalle === 'string') return detalle
  if (detalle && typeof detalle === 'object') {
    const mensajes = Object.values(detalle).flat().filter((m) => typeof m === 'string')
    if (mensajes.length) return mensajes.join(' ')
  }
  return null
}

// Traduce el problem+json del servidor al mensaje que ve la usuaria.
api.interceptors.response.use(
  (respuesta) => respuesta,
  (error) => {
    const datos = error.response?.data ?? {}
    const porCampo = datos.detail && typeof datos.detail === 'object' ? datos.detail : {}
    return Promise.reject({
      codigo: datos.codigo ?? 'error-desconocido',
      mensaje: textoDelDetalle(datos.detail) ??
        'No se pudo completar la operación. Intente nuevamente.',
      campos: porCampo,
      estado: error.response?.status
    })
  }
)
