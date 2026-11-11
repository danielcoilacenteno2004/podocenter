<script setup>
// P18 Sedes y P28 Crear o editar sede (CU02, RF03), solo para la
// administradora del centro (Práctica N.° 7, Tablas 29 y 30).
//
// El horario de atención se muestra pero no se edita: la API devuelve los
// horarios de solo lectura y no hay ninguna ruta que los escriba. Una sede
// nueva nace sin horario y, mientras no lo tenga, la agenda la trata como
// cerrada todos los días. Desactivar es desmarcar «Sede activa»; nunca se
// borra (el DELETE de la API responde 500 si la sede tiene citas).
import { computed, nextTick, onMounted, ref } from 'vue'
import { api } from '../services/api'

const DIAS = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo']
const CORTOS = ['Lun', 'Mar', 'Mié', 'Jue', 'Vie', 'Sáb', 'Dom']

const sedes = ref([])
const cargando = ref(false)
const error = ref(null)
const aviso = ref(null)

const dialogo = ref(null)
const primerCampo = ref(null)
const editando = ref(null)
const formulario = ref({})
const guardando = ref(false)
const errorFormulario = ref(null)
const camposConError = ref({})

const completo = computed(() =>
  Boolean(formulario.value.nombre?.trim() && formulario.value.direccion?.trim()))

const hora = (valor) => valor?.slice(0, 5)

function horarioDelDia (sede, dia) {
  const h = sede.horarios.find((x) => x.dia_semana === dia)
  return h && h.esta_abierta !== false ? `${hora(h.hora_apertura)} – ${hora(h.hora_cierre)}` : null
}

// «Lun a Sáb · 08:00 – 19:00»: agrupa los días seguidos con el mismo horario.
function resumenHorario (sede) {
  if (!sede.horarios.length) return null
  const tramos = []
  for (let dia = 0; dia < 7; dia++) {
    const texto = horarioDelDia(sede, dia)
    const ultimo = tramos[tramos.length - 1]
    if (ultimo && ultimo.texto === texto) ultimo.hasta = dia
    else tramos.push({ desde: dia, hasta: dia, texto })
  }
  return tramos.filter((t) => t.texto)
    .map((t) => `${CORTOS[t.desde]}${t.hasta > t.desde ? ` a ${CORTOS[t.hasta]}` : ''} · ${t.texto}`)
    .join('; ')
}

async function cargar () {
  cargando.value = true
  error.value = null
  try {
    const { data } = await api.get('/sedes/')
    sedes.value = data.results ?? data
  } catch (problema) {
    error.value = problema.mensaje
  } finally {
    cargando.value = false
  }
}

async function abrir (sede = null) {
  editando.value = sede
  errorFormulario.value = null
  camposConError.value = {}
  formulario.value = sede
    ? { nombre: sede.nombre, direccion: sede.direccion, telefono: sede.telefono, esta_activa: sede.esta_activa }
    : { nombre: '', direccion: '', telefono: '', esta_activa: true }
  dialogo.value.showModal()
  await nextTick()
  primerCampo.value?.focus()
}

async function guardar () {
  guardando.value = true
  errorFormulario.value = null
  camposConError.value = {}
  try {
    if (editando.value) {
      await api.patch(`/sedes/${editando.value.id}/`, formulario.value)
      aviso.value = `${formulario.value.nombre} actualizada.`
    } else {
      await api.post('/sedes/', formulario.value)
      aviso.value = `${formulario.value.nombre} creada. Aún no tiene horario de atención, ` +
        'así que no admite citas: el horario todavía no se puede cargar desde el sistema.'
    }
    dialogo.value.close()
    await cargar()
  } catch (problema) {
    errorFormulario.value = problema.mensaje
    camposConError.value = problema.campos ?? {}
  } finally {
    guardando.value = false
  }
}

onMounted(cargar)
</script>

<template>
  <main>
    <div class="encabezado encabezado-con-accion">
      <div>
        <h1>Sedes del centro</h1>
        <p>Una sede inactiva conserva su historial.</p>
      </div>
      <button type="button" @click="abrir()">
        + Nueva sede
      </button>
    </div>

    <p v-if="error" role="alert">
      {{ error }}
    </p>
    <p v-if="aviso" class="aviso-ok" role="status">
      {{ aviso }}
    </p>

    <section class="tarjeta">
      <p v-if="cargando" role="status">
        Cargando sedes…
      </p>
      <p v-else-if="!sedes.length" class="vacio">
        El centro todavía no tiene sedes.
      </p>
      <table v-else class="administracion">
        <caption>{{ sedes.length }} sede(s)</caption>
        <thead>
          <tr>
            <th scope="col">
              Sede
            </th>
            <th scope="col">
              Dirección
            </th>
            <th scope="col">
              Horario
            </th>
            <th scope="col">
              Activa
            </th>
            <th scope="col">
              <span class="solo-lectores">Acciones</span>
            </th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="s in sedes" :key="s.id">
            <td>
              <strong>{{ s.nombre }}</strong>
              <span v-if="s.telefono" class="secundario-celda">{{ s.telefono }}</span>
            </td>
            <td>{{ s.direccion }}</td>
            <td>
              <template v-if="resumenHorario(s)">
                {{ resumenHorario(s) }}
              </template>
              <span v-else class="etiqueta NO_ASISTIO">Sin horario</span>
            </td>
            <td>
              <span class="etiqueta" :class="s.esta_activa ? 'ATENDIDA' : 'NO_ASISTIO'">
                {{ s.esta_activa ? 'Sí' : 'No' }}
              </span>
            </td>
            <td class="accion">
              <button class="secundario boton-fila" type="button" :aria-label="`Editar ${s.nombre}`" @click="abrir(s)">
                Editar
              </button>
            </td>
          </tr>
        </tbody>
      </table>
    </section>

    <dialog ref="dialogo" class="dialogo" aria-labelledby="titulo-sede">
      <form method="dialog" class="dialogo-cabecera">
        <h2 id="titulo-sede">
          {{ editando ? `Editar ${editando.nombre}` : 'Nueva sede' }}
        </h2>
        <button class="enlace" type="submit" aria-label="Cerrar">
          ×
        </button>
      </form>
      <form class="dialogo-cuerpo" @submit.prevent="guardar">
        <div class="campo">
          <label for="s-nombre">Nombre de la sede *</label>
          <input id="s-nombre" ref="primerCampo" v-model="formulario.nombre" maxlength="80" required :aria-invalid="'nombre' in camposConError">
        </div>
        <div class="campo">
          <label for="s-direccion">Dirección *</label>
          <input id="s-direccion" v-model="formulario.direccion" maxlength="200" required :aria-invalid="'direccion' in camposConError">
        </div>
        <div class="campo">
          <label for="s-telefono">Teléfono</label>
          <input id="s-telefono" v-model="formulario.telefono" type="tel" :aria-invalid="'telefono' in camposConError">
        </div>

        <fieldset class="campo opciones">
          <legend>Horario de atención</legend>
          <template v-if="editando && editando.horarios.length">
            <dl class="horario">
              <div v-for="(nombre, dia) in DIAS" :key="dia">
                <dt>{{ nombre }}</dt>
                <dd>{{ horarioDelDia(editando, dia) ?? 'Cerrado' }}</dd>
              </div>
            </dl>
          </template>
          <p v-else class="ayuda">
            Sin horario cargado: la sede no admite citas hasta que lo tenga.
          </p>
          <p class="ayuda">
            El horario todavía no se puede modificar desde el sistema.
          </p>
        </fieldset>

        <label class="casilla">
          <input v-model="formulario.esta_activa" type="checkbox">
          <span><strong>Sede activa</strong>
            <span class="ayuda">Desactivarla la quita de la elección de sede; no borra su historial.</span></span>
        </label>

        <p v-if="errorFormulario" role="alert">
          {{ errorFormulario }}
        </p>
        <div class="dialogo-acciones">
          <button class="secundario" type="button" @click="dialogo.close()">
            Cancelar
          </button>
          <button type="submit" :disabled="!completo || guardando">
            {{ guardando ? 'Guardando…' : 'Guardar' }}
          </button>
        </div>
      </form>
    </dialog>
  </main>
</template>
