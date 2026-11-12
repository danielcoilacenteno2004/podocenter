<script setup>
// P05 Agenda de citas (CU08), con los filtros que pidió la observación de la
// Práctica N.° 7. Los filtros se resuelven en el servidor: el navegador no
// esconde filas, pide solo las que corresponden. Las opciones de cada filtro
// salen de la propia jornada, de modo que nunca se ofrece un valor que no
// tenga ninguna cita detrás.
//
// Dos vistas de la misma jornada (Práctica N.° 7): la cuadrícula por hora y
// profesional (Figura 3), para ver la forma del día, y la lista (Figura 4),
// para responder preguntas con los filtros. Las dos usan la misma respuesta.
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import AgendaCuadricula from '../components/AgendaCuadricula.vue'
import CancelarCitaDialogo from '../components/CancelarCitaDialogo.vue'
import NuevaCitaDialogo from '../components/NuevaCitaDialogo.vue'
import { api } from '../services/api'
import { useSesion } from '../stores/sesion'

const sesion = useSesion()
const ruta = useRoute()

// La agenda se puede abrir ya filtrada desde el panel del día: el enlace trae
// la fecha y, si viene del desglose por servicio, también el servicio.
const fecha = ref(ruta.query.fecha ?? new Date().toLocaleDateString('en-CA'))
const filtros = ref({
  estado: ruta.query.estado ?? '',
  profesional: ruta.query.profesional ? Number(ruta.query.profesional) : '',
  servicio: ruta.query.servicio ? Number(ruta.query.servicio) : ''
})

// La vista elegida se recuerda en este navegador; es solo una comodidad.
const vista = ref((() => {
  try { return localStorage.getItem('agenda.vista') === 'lista' ? 'lista' : 'cuadricula' } catch { return 'cuadricula' }
})())
watch(vista, (valor) => { try { localStorage.setItem('agenda.vista', valor) } catch { /* sin almacenamiento */ } })

function moverDia (dias) {
  const d = new Date(`${fecha.value}T12:00:00`)
  d.setDate(d.getDate() + dias)
  fecha.value = d.toLocaleDateString('en-CA')
}
function irAHoy () {
  fecha.value = new Date().toLocaleDateString('en-CA')
}

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

// P07 se abre sobre la cita elegida en la tabla o en la cuadrícula.
const citaACancelar = ref(null)

// En la cuadrícula, pulsar una cita la muestra con sus acciones; pulsar un
// hueco abre P06 con la hora y la profesional ya puestas (Figura 3).
const citaElegida = ref(null)
function huecoElegido ({ hora: horaDelHueco, profesional }) {
  citaElegida.value = null
  abrirNuevaCita({ hora: horaDelHueco, profesional })
}

async function citaCancelada ({ cita, plantilla }) {
  citaACancelar.value = null
  citaElegida.value = null
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

// Se ofrece registrar solo donde el servidor lo aceptaría: cita programada,
// sin atención y cuya hora ya llegó (cita-aun-no-llega). Así el botón no
// aparece dos veces ni antes de tiempo.
function atendible (cita) {
  return cita.estado === 'PROGRAMADA' && !cita.tiene_atencion &&
    new Date(cita.inicio) <= new Date()
}

const citas = ref([])
const jornada = ref([])      // el día completo, para construir las opciones
const horario = ref(null)    // apertura y cierre de la sede ese día
// Fecha a la que pertenecen `jornada` y `horario`. La cuadrícula se dibuja
// solo cuando coincide con la del selector: si no, durante la carga pintaría
// los huecos del día nuevo con las citas del día anterior.
const fechaCargada = ref(null)
const plantel = ref([])      // profesionales de la sede: columnas de la cuadrícula
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

// Una columna por profesional de la sede, tenga o no citas ese día: así se
// ven sus huecos libres. Se añade quien tenga citas sin estar ya en la lista
// (por ejemplo, una cuenta desactivada después de agendar). Con el filtro de
// profesional queda solo su columna.
const columnas = computed(() => {
  const lista = plantel.value.map((p) => ({ id: p.id, nombre: p.nombre_completo }))
  for (const p of profesionales.value) {
    if (!lista.some((c) => c.id === p.id)) lista.push(p)
  }
  return filtros.value.profesional ? lista.filter((c) => c.id === filtros.value.profesional) : lista
})
const ETIQUETAS = Object.fromEntries(ESTADOS)

async function cargarPlantel () {
  try {
    plantel.value = (await api.get('/sesion/profesionales/')).data.profesionales
  } catch {
    plantel.value = []  // la cuadrícula se arma igual con quienes tienen citas
  }
}
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
  return data
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
      ? (await pedir({
          estado: filtros.value.estado || undefined,
          profesional: filtros.value.profesional || undefined,
          servicio: filtros.value.servicio || undefined
        })).citas
      : delDia.citas
    if (mio !== turno) return
    jornada.value = delDia.citas
    horario.value = delDia.horario
    fechaCargada.value = String(delDia.fecha)
    citas.value = filtradas
    if (citaElegida.value) citaElegida.value = filtradas.find((c) => c.id === citaElegida.value.id) ?? null
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

watch(fecha, () => { citaElegida.value = null; limpiar(); cargar() })
watch(filtros, cargar, { deep: true })
onMounted(() => { cargar(); cargarPlantel() })
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
      <div class="campo campo-fecha">
        <label for="fecha">Fecha</label>
        <div class="navegar-dia">
          <button class="secundario boton-fila" type="button" aria-label="Día anterior" @click="moverDia(-1)">
            ◀
          </button>
          <input id="fecha" v-model="fecha" type="date">
          <button class="secundario boton-fila" type="button" @click="irAHoy">
            Hoy
          </button>
          <button class="secundario boton-fila" type="button" aria-label="Día siguiente" @click="moverDia(1)">
            ▶
          </button>
        </div>
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

    <div class="selector-vista" role="group" aria-label="Vista de la agenda">
      <button type="button" :class="{ secundario: vista !== 'cuadricula' }" :aria-pressed="vista === 'cuadricula'" @click="vista = 'cuadricula'">
        Cuadrícula del día
      </button>
      <button type="button" :class="{ secundario: vista !== 'lista' }" :aria-pressed="vista === 'lista'" @click="vista = 'lista'">
        Lista
      </button>
    </div>

    <section v-if="vista === 'cuadricula'" class="tarjeta">
      <p v-if="fechaCargada !== fecha" role="status">Cargando la agenda…</p>
      <template v-else>
        <p class="ayuda">
          {{ citas.length }} de {{ jornada.length }} cita(s) del día<template v-if="hayFiltros"> · filtro aplicado</template>
          <template v-if="horario"> · la sede atiende de {{ horario.apertura }} a {{ horario.cierre }}</template>
        </p>
        <div v-if="citaElegida" class="cita-elegida" role="region" aria-label="Cita elegida">
          <div>
            <strong>{{ hora(citaElegida.inicio) }} – {{ hora(citaElegida.fin) }} · {{ citaElegida.paciente_nombre }}</strong>
            <span>{{ citaElegida.servicio_nombre }} · {{ citaElegida.profesional_nombre }}</span>
            <span class="etiqueta" :class="citaElegida.estado">{{ ETIQUETAS[citaElegida.estado] ?? citaElegida.estado }}</span>
          </div>
          <div class="acciones-fila">
            <router-link
              class="boton-secundario"
              :to="{ name: 'ficha-paciente', params: { pacienteId: citaElegida.paciente } }"
            >Ficha del paciente</router-link>
            <template v-if="citaElegida.estado === 'PROGRAMADA'">
              <router-link
                v-if="atendible(citaElegida)"
                class="boton"
                :to="{ name: 'registrar-atencion', params: { citaId: citaElegida.id } }"
              >Registrar atención</router-link>
              <button class="secundario boton-fila" type="button" @click="citaACancelar = citaElegida">
                Cancelar cita
              </button>
            </template>
            <button class="enlace" type="button" aria-label="Cerrar la cita elegida" @click="citaElegida = null">
              ×
            </button>
          </div>
        </div>
        <AgendaCuadricula
          :fecha="fecha"
          :citas="citas"
          :profesionales="columnas"
          :horario="horario"
          :etiquetas="ETIQUETAS"
          :actualizando="cargando"
          @elegir="citaElegida = $event"
          @hueco="huecoElegido"
        />
      </template>
    </section>

    <section v-else class="tarjeta">
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
