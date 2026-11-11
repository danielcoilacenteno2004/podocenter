<script setup>
// P07 Cancelar cita (CU09, RF08), modal sobre la agenda (Práctica N.° 7,
// Tabla 19 y wireframe). El motivo es obligatorio; si se elige «Otro», el
// detalle también. Que la cita esté programada lo comprueba el servidor
// (cita-no-cancelable) y aquí se muestra su respuesta.
//
// La casilla de reemplazo (CC-16) viene marcada: al confirmar, la agenda
// abre P06 con el paciente, el servicio y la profesional de la cita.
import { computed, nextTick, ref, watch } from 'vue'
import { api } from '../services/api'
import { useSesion } from '../stores/sesion'

const props = defineProps({
  cita: { type: Object, default: null }
})
const emit = defineEmits(['cerrar', 'cancelada'])
const sesion = useSesion()

// Opciones del wireframe de P07; «Otro» pide escribir el detalle.
const MOTIVOS = ['El paciente avisó que no puede asistir', 'El centro reprograma']
const OTRO = 'otro'
const LIMITE = 200

const dialogo = ref(null)
const campoDetalle = ref(null)
const motivo = ref(MOTIVOS[0])
const detalle = ref('')
const crearReemplazo = ref(true)
const enviando = ref(false)
const error = ref(null)

const motivoFinal = computed(() => (motivo.value === OTRO ? detalle.value.trim() : motivo.value))
const completo = computed(() => motivoFinal.value.length > 0)

function fechaYHora (valor) {
  const d = new Date(valor)
  return `${d.toLocaleDateString('es-PE', { day: '2-digit', month: '2-digit', year: 'numeric' })} ` +
    d.toLocaleTimeString('es-PE', { hour: '2-digit', minute: '2-digit' })
}

watch(motivo, async (valor) => {
  if (valor === OTRO) {
    await nextTick()
    campoDetalle.value?.focus()
  }
})

watch(() => props.cita, (cita) => {
  if (!dialogo.value) return
  if (cita) {
    motivo.value = MOTIVOS[0]
    detalle.value = ''
    crearReemplazo.value = true
    error.value = null
    dialogo.value.showModal()
  } else if (dialogo.value.open) {
    dialogo.value.close()
  }
})

async function confirmar () {
  enviando.value = true
  error.value = null
  try {
    const { data } = await api.post(`/citas/${props.cita.id}/cancelar/`, {
      motivo: motivoFinal.value,
      crear_reemplazo: crearReemplazo.value
    })
    emit('cancelada', {
      cita: data.cita,
      plantilla: data.plantilla_reemplazo
        ? { ...data.plantilla_reemplazo, paciente: { id: props.cita.paciente, nombre: props.cita.paciente_nombre } }
        : null
    })
  } catch (problema) {
    error.value = problema.mensaje
  } finally {
    enviando.value = false
  }
}
</script>

<template>
  <dialog
    ref="dialogo"
    class="dialogo"
    aria-labelledby="titulo-cancelar"
    @close="emit('cerrar')"
  >
    <form method="dialog" class="dialogo-cabecera">
      <h2 id="titulo-cancelar">
        Cancelar cita
      </h2>
      <button class="enlace" type="submit" aria-label="Cerrar">
        ×
      </button>
    </form>

    <form v-if="cita" class="dialogo-cuerpo" @submit.prevent="confirmar">
      <div class="resumen-cita">
        <p>
          <strong>{{ cita.paciente_nombre }} · {{ fechaYHora(cita.inicio) }} · {{ cita.servicio_nombre }}</strong>
        </p>
        <p>{{ sesion.sedeActiva?.nombre }} · Profesional: {{ cita.profesional_nombre }}</p>
      </div>

      <fieldset class="campo opciones">
        <legend>Motivo de la cancelación *</legend>
        <label v-for="m in MOTIVOS" :key="m">
          <input v-model="motivo" type="radio" name="motivo" :value="m">
          {{ m }}
        </label>
        <label>
          <input v-model="motivo" type="radio" name="motivo" :value="OTRO">
          Otro (detallar)
        </label>
      </fieldset>

      <div v-if="motivo === OTRO" class="campo">
        <label for="detalle-cancelacion">Detalle *</label>
        <input
          id="detalle-cancelacion"
          ref="campoDetalle"
          v-model="detalle"
          type="text"
          :maxlength="LIMITE"
          required
          placeholder="Escriba el detalle del motivo"
        >
        <p class="ayuda">
          {{ detalle.length }} / {{ LIMITE }}
        </p>
      </div>

      <label class="casilla">
        <input v-model="crearReemplazo" type="checkbox">
        <span>
          <strong>Crear una cita de reemplazo con los mismos datos</strong>
          <span class="ayuda">Al confirmar se abre «Nueva cita» con paciente, servicio y profesional precargados.</span>
        </span>
      </label>

      <p v-if="error" role="alert">
        {{ error }}
      </p>

      <div class="dialogo-acciones">
        <button class="secundario" type="button" @click="dialogo.close()">
          Volver
        </button>
        <button type="submit" :disabled="!completo || enviando">
          {{ enviando ? 'Cancelando…' : 'Confirmar cancelación' }}
        </button>
      </div>
    </form>
  </dialog>
</template>
