// Carga el panel de un día y lo mantiene al día cuando la fecha cambia.
//
// - Los días ya vistos quedan en memoria mientras la pantalla está abierta:
//   volver a uno es instantáneo y se refresca en segundo plano, sin atenuar.
//   La memoria muere con la pantalla, así que nunca sobrevive a un cambio de
//   sede ni a un cierre de sesión.
// - Si se cambia de día varias veces seguidas, solo cuenta la respuesta del
//   último pedido: una más lenta no puede pisar al día que se está viendo.
import { computed, ref, watch } from 'vue'
import { api } from '../services/api'

export function usarPanelDelDia (fecha) {
  const memoria = new Map()
  const panel = ref(null)
  const error = ref(null)
  const pendiente = ref(false)
  const fechaMostrada = ref(null)
  let ultimoPedido = 0

  async function cargar (dia) {
    const pedido = ++ultimoPedido
    pendiente.value = true
    error.value = null
    try {
      const { data } = await api.get('/panel/', { params: { fecha: dia } })
      memoria.set(dia, data)
      if (pedido !== ultimoPedido) return
      panel.value = data
      fechaMostrada.value = dia
    } catch (problema) {
      if (pedido !== ultimoPedido) return
      error.value = problema.mensaje
      panel.value = null
      fechaMostrada.value = null
    } finally {
      if (pedido === ultimoPedido) pendiente.value = false
    }
  }

  watch(() => fecha.value, (dia) => {
    if (!dia) return
    if (memoria.has(dia)) {
      panel.value = memoria.get(dia)
      fechaMostrada.value = dia
    }
    cargar(dia)
  }, { immediate: true })

  return {
    panel,
    error,
    // Primera carga: todavía no hay nada que mostrar.
    cargando: computed(() => pendiente.value && panel.value === null),
    // Hay cifras en pantalla, pero son de otro día: se muestran atenuadas.
    actualizando: computed(() => pendiente.value && panel.value !== null && fechaMostrada.value !== fecha.value),
    recargar: () => cargar(fecha.value)
  }
}
