<script setup>
// P06 Registrar cita (CU08), modal sobre la agenda (Práctica N.° 7, Tabla 9).
// La pantalla solo recoge los datos: horario de la sede, anticipación y
// solapamiento los decide el servidor (apps/citas/servicios.py), y aquí se
// muestra su respuesta con el código que la acompaña.
//
// No incluye «Modalidad» ni «Dirección» del wireframe: la atención a
// domicilio no está modelada (docs/ESTADO.md, brecha 1). Tampoco ofrece
// horarios alternativos ante un cruce: el servidor no los calcula.
import { computed, nextTick, ref, watch } from 'vue'
import { api } from '../services/api'
import { useSesion } from '../stores/sesion'

const props = defineProps({
  abierto: { type: Boolean, default: false },
  fecha: { type: String, default: '' },
  // Cita de reemplazo (CC-16): paciente y servicio llegan precargados.
  plantilla: { type: Object, default: null }
})
const emit = defineEmits(['cerrar', 'creada'])
const sesion = useSesion()

const MINIMO_BUSQUEDA = 3
// Dónde se muestra cada error de negocio que devuelve el servidor.
const CAMPO_DEL_ERROR = {
  'cita-solapada': 'hora',
  'fuera-de-horario': 'hora',
  'cita-en-el-pasado': 'hora',
  'sede-cerrada': 'fecha',
  'profesional-sin-sede': 'profesional'
}

const dialogo = ref(null)
const campoPaciente = ref(null)

const servicios = ref([])
const profesionales = ref([])
const errorDeCarga = ref(null)

const busqueda = ref('')
const sugerencias = ref([])
const buscando = ref(false)
const buscado = ref(false)
const paciente = ref(null)

const formulario = ref({ fecha: '', hora: '', servicio: '', profesional: '' })
const guardando = ref(false)
const error = ref(null)
const campoConError = ref(null)

const hoy = () => new Date().toLocaleDateString('en-CA')
const servicioElegido = computed(() =>
  servicios.value.find((s) => s.id === formulario.value.servicio) ?? null)

const finCalculado = computed(() => {
  const { fecha, hora } = formulario.value
  if (!fecha || !hora || !servicioElegido.value) return null
  const fin = new Date(`${fecha}T${hora}:00`)
  fin.setMinutes(fin.getMinutes() + servicioElegido.value.duracion_minutos)
  return fin.toLocaleTimeString('es-PE', { hour: '2-digit', minute: '2-digit' })
})

const completo = computed(() => Boolean(paciente.value && formulario.value.fecha &&
  formulario.value.hora && formulario.value.servicio && formulario.value.profesional))

function soles (valor) {
  return `S/ ${Number(valor).toFixed(2)}`
}

async function cargarCatalogos () {
  errorDeCarga.value = null
  try {
    const [respServicios, respProfesionales] = await Promise.all([
      api.get('/servicios/', { params: { esta_activo: true } }),
      api.get('/sesion/profesionales/')
    ])
    servicios.value = respServicios.data.results ?? respServicios.data
    profesionales.value = respProfesionales.data.profesionales
  } catch (problema) {
    errorDeCarga.value = problema.mensaje
  }
}

function reiniciar () {
  const fechaInicial = props.fecha && props.fecha >= hoy() ? props.fecha : hoy()
  const propia = profesionales.value.some((p) => p.id === sesion.usuario?.id)
  formulario.value = {
    fecha: fechaInicial,
    hora: '',
    servicio: props.plantilla?.servicio ?? '',
    profesional: props.plantilla?.profesional ?? (propia ? sesion.usuario.id : '')
  }
  paciente.value = props.plantilla?.paciente ?? null
  busqueda.value = ''
  sugerencias.value = []
  buscado.value = false
  error.value = null
  campoConError.value = null
}

let temporizador = null
watch(busqueda, (texto) => {
  clearTimeout(temporizador)
  buscado.value = false
  if (texto.trim().length < MINIMO_BUSQUEDA) {
    sugerencias.value = []
    return
  }
  temporizador = setTimeout(async () => {
    buscando.value = true
    try {
      const { data } = await api.get('/pacientes/', { params: { buscar: texto.trim() } })
      sugerencias.value = (data.results ?? data).slice(0, 8)
    } catch (problema) {
      error.value = problema.mensaje
    } finally {
      buscando.value = false
      buscado.value = true
    }
  }, 300)
})

function elegirPaciente (p) {
  paciente.value = { id: p.id, nombre: `${p.nombres} ${p.apellidos}`, documento: p.documento }
  sugerencias.value = []
  busqueda.value = ''
}

async function cambiarPaciente () {
  paciente.value = null
  await nextTick()
  campoPaciente.value?.focus()
}

async function guardar () {
  guardando.value = true
  error.value = null
  campoConError.value = null
  try {
    const { data } = await api.post('/citas/', {
      sede: sesion.sedeActivaId,
      paciente: paciente.value.id,
      profesional: formulario.value.profesional,
      servicio: formulario.value.servicio,
      inicio: new Date(`${formulario.value.fecha}T${formulario.value.hora}:00`).toISOString()
    })
    emit('creada', data)
  } catch (problema) {
    error.value = problema.mensaje
    campoConError.value = CAMPO_DEL_ERROR[problema.codigo] ??
      Object.keys(problema.campos ?? {})[0] ?? null
  } finally {
    guardando.value = false
  }
}

watch(() => props.abierto, async (abierto) => {
  if (!dialogo.value) return
  if (abierto) {
    if (!servicios.value.length || !profesionales.value.length) await cargarCatalogos()
    reiniciar()
    dialogo.value.showModal()
    await nextTick()
    if (!paciente.value) campoPaciente.value?.focus()
  } else if (dialogo.value.open) {
    dialogo.value.close()
  }
})
</script>

<template>
  <dialog
    ref="dialogo"
    class="dialogo"
    aria-labelledby="titulo-nueva-cita"
    @close="emit('cerrar')"
  >
    <form method="dialog" class="dialogo-cabecera">
      <h2 id="titulo-nueva-cita">
        Nueva cita — {{ sesion.sedeActiva?.nombre }}
      </h2>
      <button class="enlace" type="submit" aria-label="Cerrar">
        ×
      </button>
    </form>

    <p v-if="errorDeCarga" role="alert">
      {{ errorDeCarga }}
    </p>

    <form v-else class="dialogo-cuerpo" @submit.prevent="guardar">
      <div class="campo">
        <label for="cita-paciente">Paciente *</label>
        <div v-if="paciente" class="elegido">
          <span><strong>{{ paciente.nombre }}</strong>
            <template v-if="paciente.documento"> · {{ paciente.documento }}</template></span>
          <button class="enlace" type="button" @click="cambiarPaciente">
            Cambiar
          </button>
        </div>
        <template v-else>
          <input
            id="cita-paciente"
            ref="campoPaciente"
            v-model="busqueda"
            type="search"
            autocomplete="off"
            placeholder="Buscar por DNI o apellido…"
            :aria-invalid="campoConError === 'paciente'"
            aria-describedby="ayuda-paciente"
          >
          <p id="ayuda-paciente" class="ayuda">
            <template v-if="busqueda.trim().length < MINIMO_BUSQUEDA">
              Escriba al menos {{ MINIMO_BUSQUEDA }} caracteres.
            </template>
            <template v-else-if="buscando">
              Buscando…
            </template>
            <template v-else-if="buscado && !sugerencias.length">
              Ningún paciente coincide. El registro de pacientes nuevos (P09) aún no está disponible.
            </template>
          </p>
          <ul v-if="sugerencias.length" class="sugerencias" aria-label="Pacientes encontrados">
            <li v-for="p in sugerencias" :key="p.id">
              <button type="button" @click="elegirPaciente(p)">
                <strong>{{ p.apellidos }}, {{ p.nombres }}</strong>
                <span>{{ p.tipo_documento }} {{ p.documento }}</span>
              </button>
            </li>
          </ul>
        </template>
      </div>

      <div class="fila-campos">
        <div class="campo">
          <label for="cita-fecha">Fecha *</label>
          <input
            id="cita-fecha"
            v-model="formulario.fecha"
            type="date"
            :min="hoy()"
            required
            :aria-invalid="campoConError === 'fecha'"
          >
        </div>
        <div class="campo">
          <label for="cita-hora">Hora de inicio *</label>
          <input
            id="cita-hora"
            v-model="formulario.hora"
            type="time"
            step="300"
            required
            :aria-invalid="campoConError === 'hora' || campoConError === 'inicio'"
          >
        </div>
      </div>

      <div class="campo">
        <label for="cita-servicio">Servicio *</label>
        <select
          id="cita-servicio"
          v-model="formulario.servicio"
          required
          :aria-invalid="campoConError === 'servicio'"
        >
          <option value="" disabled>
            Elija un servicio
          </option>
          <option v-for="s in servicios" :key="s.id" :value="s.id">
            {{ s.nombre }} — {{ soles(s.precio) }} · {{ s.duracion_minutos }} min
          </option>
        </select>
        <p v-if="finCalculado" class="ayuda">
          Fin calculado automáticamente: {{ finCalculado }}
        </p>
      </div>

      <div class="campo">
        <label for="cita-profesional">Profesional *</label>
        <select
          id="cita-profesional"
          v-model="formulario.profesional"
          required
          :aria-invalid="campoConError === 'profesional'"
        >
          <option value="" disabled>
            Elija quién atiende
          </option>
          <option v-for="p in profesionales" :key="p.id" :value="p.id">
            {{ p.nombre_completo }}
          </option>
        </select>
      </div>

      <p v-if="error" role="alert">
        {{ error }}
      </p>

      <div class="dialogo-acciones">
        <button class="secundario" type="button" @click="dialogo.close()">
          Volver
        </button>
        <button type="submit" :disabled="!completo || guardando">
          {{ guardando ? 'Guardando…' : 'Guardar cita' }}
        </button>
      </div>
    </form>
  </dialog>
</template>
