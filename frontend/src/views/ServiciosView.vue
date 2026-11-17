<script setup>
// P15 Catálogo de servicios y P26 Crear o editar servicio (CU17, RF09),
// solo para la administradora del centro (Práctica N.° 7, Tablas 23 y 24).
//
// Desactivar es desmarcar «Servicio activo»: la nueva cita (P06) solo
// ofrece los activos, el servidor rechaza citas nuevas con un servicio
// inactivo y las atenciones ya registradas lo conservan. Un servicio no se
// borra: la API no tiene DELETE.
// Los límites (precio, duración, nombre único) los valida el servidor.
//
// Insumos habituales (CC-14): los que P11 precarga al registrar la atención
// de este servicio. Se envían completos al guardar.
import { computed, nextTick, onMounted, ref } from 'vue'
import { api } from '../services/api'
import TarjetaSeccion from '../components/TarjetaSeccion.vue'

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

// Insumos habituales del formulario: [{ producto: { id, codigo, nombre, unidad }, cantidad }]
const habituales = ref([])
const productos = ref([])
const busquedaInsumo = ref('')
const sugerencias = computed(() => {
  const texto = busquedaInsumo.value.trim().toLowerCase()
  if (texto.length < 2) return []
  return productos.value.filter((p) => !habituales.value.some((h) => h.producto.id === p.id) &&
    (p.nombre.toLowerCase().includes(texto) || p.codigo.toLowerCase().includes(texto))).slice(0, 8)
})
const cantidadValida = (c) => Number.isInteger(Number(c)) && Number(c) > 0

function agregarHabitual (producto) {
  habituales.value.push({ producto, cantidad: 1 })
  busquedaInsumo.value = ''
}

const completo = computed(() => {
  const f = formulario.value
  return Boolean(f.nombre?.trim() && f.precio !== '' && f.precio !== null &&
    f.duracion_minutos !== '' && f.duracion_minutos !== null) &&
    habituales.value.every((h) => cantidadValida(h.cantidad))
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
  habituales.value = (servicio?.insumos_habituales ?? []).map((h) => ({
    producto: { id: h.producto, codigo: h.codigo, nombre: h.nombre, unidad: h.unidad },
    cantidad: h.cantidad
  }))
  busquedaInsumo.value = ''
  if (!productos.value.length) {
    try {
      productos.value = (await api.get('/inventario/productos/')).data.productos
    } catch { productos.value = [] }
  }
  dialogo.value.showModal()
  await nextTick()
  primerCampo.value?.focus()
}

async function guardar () {
  guardando.value = true
  errorFormulario.value = null
  camposConError.value = {}
  const datos = {
    ...formulario.value,
    insumos_habituales: habituales.value.map((h) => ({ producto: h.producto.id, cantidad: Number(h.cantidad) }))
  }
  try {
    if (editando.value) {
      await api.patch(`/servicios/${editando.value.id}/`, datos)
      aviso.value = `${formulario.value.nombre} actualizado.`
    } else {
      await api.post('/servicios/', datos)
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

    <TarjetaSeccion>
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
    </TarjetaSeccion>

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
        <fieldset class="campo insumos">
          <legend>Insumos habituales</legend>
          <p class="ayuda">
            Se precargan al registrar la atención de este servicio; ahí se pueden cambiar.
          </p>
          <table v-if="habituales.length" class="tabla-insumos">
            <tbody>
              <tr v-for="(h, indice) in habituales" :key="h.producto.id">
                <td>
                  <strong>{{ h.producto.nombre }}</strong>
                  <span class="secundario-celda">{{ h.producto.codigo }}</span>
                </td>
                <td class="numero">
                  <input
                    v-model="h.cantidad"
                    class="cantidad-insumo"
                    type="number"
                    min="1"
                    step="1"
                    inputmode="numeric"
                    :aria-label="`Cantidad habitual de ${h.producto.nombre}`"
                    :aria-invalid="!cantidadValida(h.cantidad)"
                  >
                  {{ h.producto.unidad }}
                </td>
                <td class="accion">
                  <button class="enlace" type="button" :aria-label="`Quitar ${h.producto.nombre}`" @click="habituales.splice(indice, 1)">
                    ×
                  </button>
                </td>
              </tr>
            </tbody>
          </table>
          <label for="sv-buscar-insumo" class="solo-lectores">Agregar insumo habitual</label>
          <input
            id="sv-buscar-insumo"
            v-model="busquedaInsumo"
            type="search"
            autocomplete="off"
            placeholder="+ Agregar insumo: código o nombre…"
          >
          <ul v-if="sugerencias.length" class="sugerencias" aria-label="Productos encontrados">
            <li v-for="p in sugerencias" :key="p.id">
              <button type="button" @click="agregarHabitual(p)">
                <strong>{{ p.nombre }}</strong>
                <span>{{ p.codigo }}</span>
              </button>
            </li>
          </ul>
        </fieldset>

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
