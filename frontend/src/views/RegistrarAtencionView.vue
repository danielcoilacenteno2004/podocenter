<script setup>
// P11 Registrar atención (CU10). El requisito que manda es el RNF02: cinco
// interacciones o menos desde la agenda hasta el guardado. Por eso paciente,
// servicio y profesional llegan precargados de la cita y lo único que se
// escribe es la observación clínica, con el foco ya puesto en ella.
//
// Los antecedentes del paciente van en la cabecera, encima del formulario:
// antes de tocar un pie diabético hay que verlos sin cambiar de pantalla.
import { computed, nextTick, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '../services/api'

const props = defineProps({ citaId: { type: String, required: true } })
const router = useRouter()

// Límite de la especificación de P11 (Práctica N.° 7, Tabla 10).
const LIMITE = 2000

const cita = ref(null)
const paciente = ref(null)
const observaciones = ref('')
const cargando = ref(true)
const guardando = ref(false)
const errorDeCarga = ref(null)
const errorAlGuardar = ref(null)
const campoNotas = ref(null)

// La interfaz no ofrece la acción cuando sabe que el servidor la rechazará.
const aunNoLlega = computed(() => cita.value && new Date(cita.value.inicio) > new Date())
const atendible = computed(() =>
  cita.value?.estado === 'PROGRAMADA' && !cita.value?.tiene_atencion && !aunNoLlega.value)

function hora (valor) {
  return new Date(valor).toLocaleTimeString('es-PE', { hour: '2-digit', minute: '2-digit' })
}

function fechaLarga (valor) {
  return new Date(valor).toLocaleDateString('es-PE', { weekday: 'long', day: 'numeric', month: 'long' })
}

function edad (fecha) {
  if (!fecha) return null
  const nacimiento = new Date(fecha)
  const hoy = new Date()
  let años = hoy.getFullYear() - nacimiento.getFullYear()
  const mes = hoy.getMonth() - nacimiento.getMonth()
  if (mes < 0 || (mes === 0 && hoy.getDate() < nacimiento.getDate())) años -= 1
  return años
}

async function cargar () {
  cargando.value = true
  errorDeCarga.value = null
  try {
    const { data } = await api.get(`/citas/${props.citaId}/`)
    cita.value = data
    // Lectura de la ficha clínica: el servidor la deja en la auditoría.
    paciente.value = (await api.get(`/pacientes/${data.paciente}/`)).data
  } catch (problema) {
    errorDeCarga.value = problema.mensaje
  } finally {
    cargando.value = false
  }
  if (atendible.value) {
    await nextTick()
    campoNotas.value?.focus()
  }
}

async function confirmar () {
  guardando.value = true
  errorAlGuardar.value = null
  try {
    await api.post('/atenciones/', {
      cita: cita.value.id,
      observaciones_clinicas: observaciones.value.trim()
    })
    router.push({
      name: 'agenda',
      query: { fecha: cita.value.inicio.slice(0, 10), aviso: 'atencion-registrada' }
    })
  } catch (problema) {
    errorAlGuardar.value = problema.mensaje
    guardando.value = false
  }
}

onMounted(cargar)
</script>

<template>
  <main>
    <div class="encabezado">
      <router-link :to="{ name: 'agenda', query: cita ? { fecha: cita.inicio.slice(0, 10) } : {} }">
        ← Volver a la agenda
      </router-link>
      <h1>Registrar atención</h1>
    </div>

    <p v-if="cargando" role="status">Cargando la cita y la ficha del paciente…</p>

    <div v-else-if="errorDeCarga" role="alert">
      {{ errorDeCarga }}
      <button class="secundario" type="button" @click="cargar">Reintentar</button>
    </div>

    <template v-else>
      <section class="tarjeta cabecera-atencion" aria-labelledby="titulo-paciente">
        <div class="cabecera-datos">
          <h2 id="titulo-paciente">{{ paciente.nombres }} {{ paciente.apellidos }}</h2>
          <p>
            {{ paciente.tipo_documento }} {{ paciente.documento }}
            <template v-if="edad(paciente.fecha_nacimiento) !== null">
              · {{ edad(paciente.fecha_nacimiento) }} años
            </template>
          </p>
          <dl class="datos-cita">
            <div><dt>Cita</dt><dd>{{ fechaLarga(cita.inicio) }}, {{ hora(cita.inicio) }} – {{ hora(cita.fin) }}</dd></div>
            <div><dt>Servicio</dt><dd>{{ cita.servicio_nombre }}</dd></div>
            <div><dt>Profesional</dt><dd>{{ cita.profesional_nombre }}</dd></div>
          </dl>
        </div>

        <div id="antecedentes" class="antecedentes" :class="{ vacios: !paciente.antecedentes }">
          <h3>Antecedentes</h3>
          <p v-if="paciente.antecedentes">{{ paciente.antecedentes }}</p>
          <p v-else>Sin antecedentes registrados en la ficha.</p>
        </div>
      </section>

      <p v-if="!atendible" role="alert">
        {{ cita.tiene_atencion
          ? 'Esta cita ya tiene su atención registrada.'
          : cita.estado !== 'PROGRAMADA'
            ? 'Solo se registra la atención de una cita programada.'
            : 'La cita todavía no llega: la atención se registra cuando llega la hora.' }}
      </p>

      <form v-else class="tarjeta" aria-label="Atención" @submit.prevent="confirmar">
        <div class="campo">
          <label for="observaciones">Observación clínica</label>
          <textarea
            id="observaciones"
            ref="campoNotas"
            v-model="observaciones"
            rows="6"
            :maxlength="LIMITE"
            aria-describedby="antecedentes ayuda-observaciones"
            placeholder="Lo que se encontró y lo que se hizo en esta atención"
          />
          <p id="ayuda-observaciones" class="ayuda">
            Opcional. Se guarda cifrada. {{ observaciones.length }} / {{ LIMITE }}
          </p>
        </div>

        <p v-if="errorAlGuardar" role="alert">{{ errorAlGuardar }}</p>

        <button type="submit" :disabled="guardando">
          {{ guardando ? 'Guardando…' : 'Confirmar atención' }}
        </button>
      </form>
    </template>
  </main>
</template>
