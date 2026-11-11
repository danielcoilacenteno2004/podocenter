<script setup>
// P25 Detalle de atención (CU07, RF05), modal sobre la ficha del paciente
// (Práctica N.° 7, Tabla 20). Solo lectura: corregir una atención exige
// anularla, y esa acción no existe todavía.
//
// La nota clínica solo sale por GET /atenciones/{id}/, que deja cada
// apertura en la bitácora de auditoría; el listado del historial no la trae.
// Del wireframe no se construyen el monto, los bloques separados de
// diagnóstico y tratamiento ni la tabla de insumos: la atención guarda una
// sola observación clínica y no tiene cobro ni insumos.
import { ref, watch } from 'vue'
import { api } from '../services/api'

const props = defineProps({
  atencionId: { type: Number, default: null }
})
const emit = defineEmits(['cerrar'])

const dialogo = ref(null)
const atencion = ref(null)
const cargando = ref(false)
const error = ref(null)

function fechaLarga (valor) {
  return new Date(valor).toLocaleDateString('es-PE', { day: '2-digit', month: '2-digit', year: 'numeric' })
}

watch(() => props.atencionId, async (id) => {
  if (!dialogo.value) return
  if (id === null) {
    if (dialogo.value.open) dialogo.value.close()
    return
  }
  atencion.value = null
  error.value = null
  cargando.value = true
  dialogo.value.showModal()
  try {
    atencion.value = (await api.get(`/atenciones/${id}/`)).data
  } catch (problema) {
    error.value = problema.mensaje
  } finally {
    cargando.value = false
  }
})
</script>

<template>
  <dialog
    ref="dialogo"
    class="dialogo"
    aria-labelledby="titulo-atencion"
    @close="emit('cerrar')"
  >
    <form method="dialog" class="dialogo-cabecera">
      <h2 id="titulo-atencion">
        <template v-if="atencion">
          Atención del {{ fechaLarga(atencion.registrada_en) }} · {{ atencion.paciente_nombre }}
        </template>
        <template v-else>
          Detalle de atención
        </template>
      </h2>
      <button class="enlace" type="submit" aria-label="Cerrar">
        ×
      </button>
    </form>

    <div class="dialogo-cuerpo">
      <p v-if="cargando" role="status">
        Cargando la atención…
      </p>
      <p v-else-if="error" role="alert">
        {{ error }}
      </p>
      <template v-else-if="atencion">
        <p class="resumen-atencion">
          {{ atencion.sede_nombre }} · {{ atencion.profesional_nombre }} · {{ atencion.servicio_nombre }}
        </p>
        <section class="antecedentes" :class="{ vacios: !atencion.observaciones_clinicas }" aria-labelledby="titulo-observacion">
          <h3 id="titulo-observacion">
            Observación clínica (dato sensible, cifrado)
          </h3>
          <p v-if="atencion.observaciones_clinicas">
            {{ atencion.observaciones_clinicas }}
          </p>
          <p v-else>
            No se registró observación en esta atención.
          </p>
        </section>
        <p class="ayuda">
          Solo lectura. Esta consulta queda registrada en la bitácora de auditoría.
        </p>
      </template>

      <div class="dialogo-acciones">
        <button class="secundario" type="button" @click="dialogo.close()">
          Cerrar
        </button>
      </div>
    </div>
  </dialog>
</template>
