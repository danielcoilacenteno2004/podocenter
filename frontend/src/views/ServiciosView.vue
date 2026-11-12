<script setup>
// P15 Catálogo de servicios y P26 Crear o editar servicio (CU17, RF09),
// solo para la administradora del centro (Práctica N.° 7, Tablas 23 y 24).
//
// Desactivar es desmarcar «Servicio activo»: la nueva cita (P06) solo
// ofrece los activos, el servidor rechaza citas nuevas con un servicio
// inactivo y las atenciones ya registradas lo conservan. Un servicio no se
// borra: la API no tiene DELETE.
// Los límites (precio, duración, nombre único) los valida el servidor.
import { computed, nextTick, onMounted, ref } from 'vue'
import { api } from '../services/api'

const servicios = ref([])
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

const completo = computed(() => {
  const f = formulario.value
  return Boolean(f.nombre?.trim() && f.precio !== '' && f.precio !== null &&
    f.duracion_minutos !== '' && f.duracion_minutos !== null)
})

const soles = (valor) => `S/ ${Number(valor).toFixed(2)}`

async function cargar () {
  cargando.value = true
  error.value = null
  try {
    const { data } = await api.get('/servicios/')
    servicios.value = data.results ?? data
  } catch (problema) {
    error.value = problema.mensaje
  } finally {
    cargando.value = false
  }
}

async function abrir (servicio = null) {
  editando.value = servicio
  errorFormulario.value = null
  camposConError.value = {}
  formulario.value = servicio
    ? {
        nombre: servicio.nombre,
        descripcion: servicio.descripcion,
        precio: servicio.precio,
        duracion_minutos: servicio.duracion_minutos,
        esta_activo: servicio.esta_activo
      }
    : { nombre: '', descripcion: '', precio: '', duracion_minutos: '', esta_activo: true }
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
      await api.patch(`/servicios/${editando.value.id}/`, formulario.value)
      aviso.value = `${formulario.value.nombre} actualizado.`
    } else {
      await api.post('/servicios/', formulario.value)
      aviso.value = `${formulario.value.nombre} agregado al catálogo.`
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
        <h1>Catálogo de servicios</h1>
        <p>Un servicio inactivo no se ofrece en citas nuevas.</p>
      </div>
      <button type="button" @click="abrir()">
        + Nuevo servicio
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
        Cargando el catálogo…
      </p>
      <p v-else-if="!servicios.length" class="vacio">
        El catálogo todavía está vacío.
      </p>
      <table v-else class="administracion">
        <caption>{{ servicios.length }} servicio(s)</caption>
        <thead>
          <tr>
            <th scope="col">
              Servicio
            </th>
            <th scope="col">
              Precio
            </th>
            <th scope="col">
              Duración
            </th>
            <th scope="col">
              Activo
            </th>
            <th scope="col">
              <span class="solo-lectores">Acciones</span>
            </th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="s in servicios" :key="s.id">
            <td>
              <strong>{{ s.nombre }}</strong>
              <span v-if="s.descripcion" class="secundario-celda">{{ s.descripcion }}</span>
            </td>
            <td class="numero">
              {{ soles(s.precio) }}
            </td>
            <td class="numero">
              {{ s.duracion_minutos }} min
            </td>
            <td>
              <span class="etiqueta" :class="s.esta_activo ? 'ATENDIDA' : 'NO_ASISTIO'">
                {{ s.esta_activo ? 'Sí' : 'No' }}
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

    <dialog ref="dialogo" class="dialogo" aria-labelledby="titulo-servicio">
      <form method="dialog" class="dialogo-cabecera">
        <h2 id="titulo-servicio">
          {{ editando ? `Editar ${editando.nombre}` : 'Nuevo servicio' }}
        </h2>
        <button class="enlace" type="submit" aria-label="Cerrar">
          ×
        </button>
      </form>
      <form class="dialogo-cuerpo" @submit.prevent="guardar">
        <div class="campo">
          <label for="sv-nombre">Nombre del servicio *</label>
          <input id="sv-nombre" ref="primerCampo" v-model="formulario.nombre" maxlength="100" required :aria-invalid="'nombre' in camposConError">
        </div>
        <div class="campo">
          <label for="sv-descripcion">Descripción</label>
          <input id="sv-descripcion" v-model="formulario.descripcion" maxlength="300" :aria-invalid="'descripcion' in camposConError">
        </div>
        <div class="fila-campos">
          <div class="campo">
            <label for="sv-precio">Precio (S/) *</label>
            <input id="sv-precio" v-model="formulario.precio" type="number" step="0.01" inputmode="decimal" required :aria-invalid="'precio' in camposConError">
          </div>
          <div class="campo">
            <label for="sv-duracion">Duración (min) *</label>
            <input id="sv-duracion" v-model.number="formulario.duracion_minutos" type="number" min="10" max="240" step="1" inputmode="numeric" required aria-describedby="ayuda-duracion" :aria-invalid="'duracion_minutos' in camposConError">
            <p id="ayuda-duracion" class="ayuda">
              Entre 10 y 240 minutos.
            </p>
          </div>
        </div>
        <label class="casilla">
          <input v-model="formulario.esta_activo" type="checkbox">
          <span><strong>Servicio activo</strong>
            <span class="ayuda">Desactivarlo no borra: conserva las atenciones ya registradas.</span></span>
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
