<script setup>
// P10 Ficha e historial del paciente (CU07), según el wireframe y la Tabla 15
// de la Práctica N.° 7, en el orden en que la podóloga consulta al paciente:
// datos, antecedentes, historial. Los antecedentes van arriba y desplegados,
// como en P11; la Práctica 7 los registra para esta pantalla («antes de tocar
// un pie diabético necesito ver los antecedentes»).
//
// Abrir la ficha queda en la bitácora de auditoría: lo registra el servidor
// al responder GET /pacientes/{id}/.
//
// Del wireframe no se construyen aún: «Editar paciente» (P09), «Ver
// evidencia» del consentimiento, el filtro por año, las columnas Monto e
// Insumos (no existen en la atención) y «Ver detalle» (P25).
import { onMounted, ref } from 'vue'
import { api } from '../services/api'

const props = defineProps({ pacienteId: { type: String, required: true } })

const paciente = ref(null)
const atenciones = ref([])
const siguiente = ref(null)
const total = ref(0)
const cargando = ref(true)
const cargandoMas = ref(false)
const error = ref(null)

function edad (fecha) {
  if (!fecha) return null
  const nacimiento = new Date(fecha)
  const hoy = new Date()
  let años = hoy.getFullYear() - nacimiento.getFullYear()
  const mes = hoy.getMonth() - nacimiento.getMonth()
  if (mes < 0 || (mes === 0 && hoy.getDate() < nacimiento.getDate())) años -= 1
  return años
}

function fechaCorta (valor) {
  return new Date(valor).toLocaleDateString('es-PE', { day: '2-digit', month: '2-digit', year: 'numeric' })
}

async function cargar () {
  cargando.value = true
  error.value = null
  try {
    const [ficha, historial] = await Promise.all([
      api.get(`/pacientes/${props.pacienteId}/`),
      api.get('/atenciones/', { params: { paciente: props.pacienteId } })
    ])
    paciente.value = ficha.data
    atenciones.value = historial.data.results
    siguiente.value = historial.data.next
    total.value = historial.data.count
  } catch (problema) {
    error.value = problema.mensaje
  } finally {
    cargando.value = false
  }
}

async function verMas () {
  cargandoMas.value = true
  try {
    // `next` es absoluto; se pide solo su ruta para pasar por el mismo cliente.
    const url = new URL(siguiente.value)
    const { data } = await api.get(url.pathname.replace(/^\/api\/v1/, '') + url.search)
    atenciones.value.push(...data.results)
    siguiente.value = data.next
  } catch (problema) {
    error.value = problema.mensaje
  } finally {
    cargandoMas.value = false
  }
}

onMounted(cargar)
</script>

<template>
  <main>
    <div class="encabezado">
      <router-link :to="{ name: 'pacientes' }">
        ← Volver a pacientes
      </router-link>
    </div>

    <p v-if="cargando" role="status">
      Cargando la ficha del paciente…
    </p>

    <div v-else-if="error && !paciente" role="alert">
      {{ error }}
      <button class="secundario" type="button" @click="cargar">
        Reintentar
      </button>
    </div>

    <template v-else>
      <div class="encabezado">
        <h1>{{ paciente.nombres }} {{ paciente.apellidos }}</h1>
        <p>
          {{ paciente.tipo_documento }} {{ paciente.documento }}
          <template v-if="edad(paciente.fecha_nacimiento) !== null">
            · {{ edad(paciente.fecha_nacimiento) }} años
          </template>
          <template v-if="paciente.telefono">
            · {{ paciente.telefono }}
          </template>
          <template v-if="paciente.correo">
            · {{ paciente.correo }}
          </template>
        </p>
      </div>

      <div class="bloques-ficha">
        <section class="antecedentes" :class="{ vacios: !paciente.antecedentes }" aria-labelledby="titulo-antecedentes">
          <h2 id="titulo-antecedentes">
            Antecedentes clínicos
          </h2>
          <p v-if="paciente.antecedentes">
            {{ paciente.antecedentes }}
          </p>
          <p v-else>
            Sin antecedentes registrados en la ficha.
          </p>
        </section>

        <section class="consentimiento" aria-labelledby="titulo-consentimiento">
          <template v-if="paciente.consentimiento_vigente">
            <h2 id="titulo-consentimiento">
              Consentimiento {{ paciente.consentimiento_vigente.version_texto }}
              aceptado el {{ fechaCorta(paciente.consentimiento_vigente.otorgado_en) }}
            </h2>
            <p>
              Tratamiento de datos:
              <strong>{{ paciente.consentimiento_vigente.acepta_tratamiento_datos ? 'autorizado' : 'no autorizado' }}</strong>
              · Recordatorios:
              <strong>{{ paciente.consentimiento_vigente.acepta_recordatorios ? 'autorizados' : 'no autorizados' }}</strong>
            </p>
          </template>
          <template v-else>
            <h2 id="titulo-consentimiento">
              Sin consentimiento vigente
            </h2>
            <p>No se le envían recordatorios.</p>
          </template>
        </section>
      </div>

      <p v-if="error" role="alert">
        {{ error }}
      </p>

      <section class="tarjeta" aria-labelledby="titulo-historial">
        <h2 id="titulo-historial">
          Historial de atenciones · todas las sedes del centro
        </h2>
        <p v-if="!atenciones.length" class="vacio">
          Este paciente todavía no tiene atenciones registradas.
        </p>
        <table v-else>
          <caption>{{ atenciones.length }} de {{ total }} atención(es), de la más reciente a la más antigua</caption>
          <thead>
            <tr>
              <th scope="col">
                Fecha
              </th>
              <th scope="col">
                Sede
              </th>
              <th scope="col">
                Servicio
              </th>
              <th scope="col">
                Profesional
              </th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="atencion in atenciones" :key="atencion.id">
              <td class="numero">
                {{ fechaCorta(atencion.registrada_en) }}
              </td>
              <td>{{ atencion.sede_nombre }}</td>
              <td>{{ atencion.servicio_nombre }}</td>
              <td>{{ atencion.profesional_nombre }}</td>
            </tr>
          </tbody>
        </table>
        <button v-if="siguiente" class="secundario ver-mas" type="button" :disabled="cargandoMas" @click="verMas">
          {{ cargandoMas ? 'Cargando…' : 'Ver más' }}
        </button>
      </section>
    </template>
  </main>
</template>
