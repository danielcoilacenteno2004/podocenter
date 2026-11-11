<script setup>
// P05 Agenda de citas (CU08), con los filtros que pidió la observación de la
// Práctica N.° 7. Los filtros se resuelven en el servidor: el navegador no
// esconde filas, pide solo las que corresponden. Las opciones de cada filtro
// salen de la propia jornada, de modo que nunca se ofrece un valor que no
// tenga ninguna cita detrás.
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import CancelarCitaDialogo from '../components/CancelarCitaDialogo.vue'
import NuevaCitaDialogo from '../components/NuevaCitaDialogo.vue'
import { api } from '../services/api'
import { useSesion } from '../stores/sesion'

const sesion = useSesion()
const ruta = useRoute()

// La agenda se puede abrir ya filtrada desde el panel del día: el enlace trae
// la fecha y, si viene del desglose por servicio, también el servicio.
const fecha = ref(ruta.query.fecha ?? new Date().toISOString().slice(0, 10))
const filtros = ref({
  estado: ruta.query.estado ?? '',
  profesional: ruta.query.profesional ? Number(ruta.query.profesional) : '',
  servicio: ruta.query.servicio ? Number(ruta.query.servicio) : ''
})

// Al volver de P11 la agenda confirma el registro; la fila ya aparece atendida.
const aviso = ref(ruta.query.aviso === 'atencion-registrada' ? 'Atención registrada.' : null)

// P06 se abre como modal sobre la agenda, «sin horario precargado». Si viene
// de cancelar con reemplazo (P07, CC-16), trae paciente y servicio.
const nuevaCitaAbierta = ref(false)
const plantillaNuevaCita = ref(null)

function abrirNuevaCita (plantilla = null) {
  plantillaNuevaCita.value = plantilla
  nuevaCitaAbierta.value = true
}

function cerrarNuevaCita () {
  nuevaCitaAbierta.value = false
  plantillaNuevaCita.value = null
}

// P07 se abre sobre la cita elegida en la tabla.
const citaACancelar = ref(null)

async function citaCancelada ({ cita, plantilla }) {
  citaACancelar.value = null
  aviso.value = `Cita cancelada: ${cita.paciente_nombre}, a las ${hora(cita.inicio)}`
  await cargar()
  if (plantilla) abrirNuevaCita(plantilla)
}

async function citaCreada (cita) {
  cerrarNuevaCita()
  aviso.value = `Cita registrada: ${cita.paciente_nombre}, a las ${hora(cita.inicio)}`
  const dia = cita.inicio.slice(0, 10)
  if (dia !== fecha.value) fecha.value = dia  // el watch recarga la jornada
  else await cargar()
}

// Se ofrece registrar solo donde el servidor lo aceptaría: cita programada y
// sin atención. Así el botón no aparece dos veces para la misma cita.
function atendible (cita) {
  return cita.estado === 'PROGRAMADA' && !cita.tiene_atencion
}

const citas = ref([])
const jornada = ref([])      // el día completo, para construir las opciones
const cargando = ref(false)
const error = ref(null)

const ESTADOS = [
  ['PROGRAMADA', 'Programada'],
  ['ATENDIDA', 'Atendida'],
  ['CANCELADA', 'Cancelada'],
  ['NO_ASISTIO', 'No asistió']
]

function opciones (campoId, campoNombre) {
  const vistos = new Map()
  for (const cita of jornada.value) {
    if (cita[campoId] != null) vistos.set(cita[campoId], cita[campoNombre])
  }
  return [...vistos].map(([id, nombre]) => ({ id, nombre }))
}
const profesionales = computed(() => opciones('profesional', 'profesional_nombre'))
const servicios = computed(() => opciones('servicio', 'servicio_nombre'))

const hayFiltros = computed(() => Object.values(filtros.value).some(Boolean))
const estadosPresentes = computed(() => {
  const cuenta = {}
  for (const cita of jornada.value) cuenta[cita.estado] = (cuenta[cita.estado] ?? 0) + 1
  return cuenta
})

function hora (valor) {
  return new Date(valor).toLocaleTimeString('es-PE', { hour: '2-digit', minute: '2-digit' })
}

async function pedir (params) {
  const { data } = await api.get('/citas/agenda/', { params: { fecha: fecha.value, ...params } })
  return data.citas
}

// Cambiar la fecha o un filtro dispara una carga nueva sin esperar a que
// termine la anterior. Cada carga lleva su turno y solo pinta la última
// pedida: si no, una respuesta lenta del día anterior podía llegar después y
// dejar en la tabla las citas de otra fecha que la que muestra el selector.
let turno = 0

async function cargar () {
  const mio = ++turno
  cargando.value = true
  error.value = null
  try {
    const delDia = await pedir({})
    const filtradas = hayFiltros.value
      ? await pedir({
          estado: filtros.value.estado || undefined,
          profesional: filtros.value.profesional || undefined,
          servicio: filtros.value.servicio || undefined
        })
      : delDia
    if (mio !== turno) return
    jornada.value = delDia
    citas.value = filtradas
  } catch (problema) {
    if (mio !== turno) return
    error.value = problema.mensaje
    citas.value = []
  } finally {
    if (mio === turno) cargando.value = false
  }
}

function limpiar () {
  filtros.value = { estado: '', profesional: '', servicio: '' }
}

watch(fecha, () => { limpiar(); cargar() })
watch(filtros, cargar, { deep: true })
onMounted(cargar)
</script>

<template>
  <main>
    <div class="encabezado encabezado-con-accion">
      <div>
        <h1>Agenda de citas</h1>
        <p v-if="sesion.sedeActiva">{{ sesion.sedeActiva.nombre }} — {{ sesion.sedeActiva.direccion }}</p>
      </div>
      <button type="button" :disabled="!sesion.sedeActiva" @click="abrirNuevaCita()">
        + Nueva cita
      </button>
    </div>

    <form class="filtros" aria-label="Filtros de la agenda" @submit.prevent="cargar">
      <div class="campo">
        <label for="fecha">Fecha</label>
        <input id="fecha" v-model="fecha" type="date">
      </div>

      <div class="campo">
        <label for="estado">Estado</label>
        <select id="estado" v-model="filtros.estado">
          <option value="">Todos</option>
          <option v-for="[valor, etiqueta] in ESTADOS" :key="valor" :value="valor">
            {{ etiqueta }}<template v-if="estadosPresentes[valor]"> ({{ estadosPresentes[valor] }})</template>
          </option>
        </select>
      </div>

      <div class="campo">
        <label for="profesional">Profesional</label>
        <select id="profesional" v-model="filtros.profesional">
          <option value="">Todas</option>
          <option v-for="p in profesionales" :key="p.id" :value="p.id">{{ p.nombre }}</option>
        </select>
      </div>

      <div class="campo">
        <label for="servicio">Servicio</label>
        <select id="servicio" v-model="filtros.servicio">
          <option value="">Todos</option>
          <option v-for="s in servicios" :key="s.id" :value="s.id">{{ s.nombre }}</option>
        </select>
      </div>

      <button v-if="hayFiltros" class="secundario" type="button" @click="limpiar">
        Quitar filtros
      </button>
    </form>

    <p v-if="error" role="alert">{{ error }}</p>
    <p v-if="aviso" class="aviso-ok" role="status">{{ aviso }}</p>

    <section class="tarjeta">
      <p v-if="cargando" role="status">Cargando la agenda…</p>
      <p v-else-if="!citas.length" class="vacio">
        {{ hayFiltros
          ? 'Ninguna cita del día coincide con los filtros elegidos.'
          : 'No hay citas programadas para esta fecha.' }}
      </p>
      <table v-else class="agenda">
        <caption>
          {{ citas.length }} de {{ jornada.length }} cita(s) del día
          <template v-if="hayFiltros"> · filtro aplicado</template>
        </caption>
        <thead>
          <tr>
            <th scope="col">Hora</th>
            <th scope="col">Paciente</th>
            <th scope="col">Servicio</th>
            <th scope="col">Profesional</th>
            <th scope="col">Estado</th>
            <th scope="col"><span class="solo-lectores">Acción</span></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="cita in citas" :key="cita.id">
            <td class="numero hora">{{ hora(cita.inicio) }} – {{ hora(cita.fin) }}</td>
            <td class="paciente">{{ cita.paciente_nombre }}</td>
            <td class="detalle">{{ cita.servicio_nombre }}</td>
            <td class="detalle">{{ cita.profesional_nombre }}</td>
            <td class="estado"><span class="etiqueta" :class="cita.estado">
              {{ (ESTADOS.find(([v]) => v === cita.estado) ?? [])[1] ?? cita.estado }}
            </span></td>
            <td class="accion">
              <div v-if="cita.estado === 'PROGRAMADA'" class="acciones-fila">
                <router-link
                  v-if="atendible(cita)"
                  class="boton"
                  :to="{ name: 'registrar-atencion', params: { citaId: cita.id } }"
                  :aria-label="`Registrar atención de ${cita.paciente_nombre}`"
                >Registrar atención</router-link>
                <button
                  class="secundario boton-fila"
                  type="button"
                  :aria-label="`Cancelar la cita de ${cita.paciente_nombre}`"
                  @click="citaACancelar = cita"
                >
                  Cancelar
                </button>
              </div>
            </td>
          </tr>
        </tbody>
      </table>
    </section>
    <NuevaCitaDialogo
      :abierto="nuevaCitaAbierta"
      :fecha="fecha"
      :plantilla="plantillaNuevaCita"
      @cerrar="cerrarNuevaCita"
      @creada="citaCreada"
    />
    <CancelarCitaDialogo
      :cita="citaACancelar"
      @cerrar="citaACancelar = null"
      @cancelada="citaCancelada"
    />
  </main>
</template>
