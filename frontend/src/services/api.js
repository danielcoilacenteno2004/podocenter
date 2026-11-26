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
  async (error) => {
    let datos = error.response?.data ?? {}
    // En una descarga (responseType 'blob') el error también llega como
    // archivo: se lee para no perder el código estable del servidor.
    if (typeof Blob !== 'undefined' && datos instanceof Blob) {
      try { datos = JSON.parse(await datos.text()) } catch { datos = {} }
    }
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

// Descarga un archivo que genera el servidor (RF16) con el nombre que este
// propone. Pasa por el mismo cliente para llevar la sede activa y la cookie.
export async function descargarArchivo (ruta, params) {
  const respuesta = await api.get(ruta, { params, responseType: 'blob' })
  const disposicion = respuesta.headers['content-disposition'] ?? ''
  const nombre = /filename="([^"]+)"/.exec(disposicion)?.[1] ?? 'descarga'
  const url = URL.createObjectURL(respuesta.data)
  const enlace = document.createElement('a')
  enlace.href = url
  enlace.download = nombre
  document.body.appendChild(enlace)
  enlace.click()
  enlace.remove()
  URL.revokeObjectURL(url)
}
