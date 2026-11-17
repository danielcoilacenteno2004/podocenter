// Cifra que pasa de su valor anterior al nuevo en una animación breve, para
// que al cambiar de día se perciba qué subió y qué bajó. Quien pide menos
// movimiento al sistema operativo ve el valor final directamente.
import { onBeforeUnmount, ref, watch } from 'vue'

const prefiereSinMovimiento = () =>
  window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false

export function usarCifraAnimada (fuente, duracionMs = 650) {
  const valor = ref(0)
  let cuadro = null

  watch(fuente, (destino) => {
    cancelAnimationFrame(cuadro)
    const meta = Number(destino) || 0
    if (prefiereSinMovimiento()) {
      valor.value = meta
      return
    }
    const desde = valor.value
    const inicio = performance.now()
    const avanzar = (ahora) => {
      const progreso = Math.min((ahora - inicio) / duracionMs, 1)
      const suavizado = 1 - (1 - progreso) ** 3
      valor.value = desde + (meta - desde) * suavizado
      if (progreso < 1) cuadro = requestAnimationFrame(avanzar)
    }
    cuadro = requestAnimationFrame(avanzar)
  }, { immediate: true })

  onBeforeUnmount(() => cancelAnimationFrame(cuadro))
  return valor
}
