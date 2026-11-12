<script setup>
// P11 Registrar atención (CU10). El requisito que manda es el RNF02: cinco
// interacciones o menos desde la agenda hasta el guardado. Por eso paciente,
// servicio y profesional llegan precargados de la cita y lo único que se
// escribe es la observación clínica, con el foco ya puesto en ella.
//
// Los antecedentes del paciente van en la cabecera, encima del formulario:
// antes de tocar un pie diabético hay que verlos sin cambiar de pantalla.
//
// Insumos consumidos (Tabla 10): cada fila muestra el stock de la sede y se
// resalta si la cantidad lo supera; entonces se puede ver la otra sede (P14)
// y no se deja confirmar. El servidor descuenta el stock en la misma
// transacción que la atención y vuelve a comprobarlo con la fila bloqueada.
// No se precargan los insumos habituales del servicio: CC-14 no está
// construido, así que cada insumo suma una interacción al RNF02.
import { computed, nextTick, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import DisponibilidadDialogo from '../components/DisponibilidadDialogo.vue'
import { api } from '../services/api'

const props = defineProps({ citaId: { type: String, required: true } })
const router = useRouter()

// Límite de la especificación de P11 (Práctica N.° 7, Tabla 10).
const LIMITE = 2000

const cita = ref(null)
const paciente = ref(null)
const observaciones = ref('')
// Precargado con el precio del servicio y editable (Práctica 7, Tabla 10): lo
// que se guarda es lo que se cobró de verdad, que alimenta el registro diario.
const monto = ref('')
const montoConError = ref(false)
const cargando = ref(true)
const guardando = ref(false)
const errorDeCarga = ref(null)
const errorAlGuardar = ref(null)
const campoNotas = ref(null)

// Insumos: catálogo con el stock de la sede activa, y las filas elegidas.
const stock = ref([])
const errorDeStock = ref(null)
const insumos = ref([])          // [{ producto: fila de stock, cantidad }]
const busquedaInsumo = ref('')
const productoConsultado = ref(null)

const sugerenciasInsumo = computed(() => {
  const texto = busquedaInsumo.value.trim().toLowerCase()
  if (texto.length < 2) return []
  return stock.value.filter((p) => !insumos.value.some((i) => i.producto.id === p.id) &&
    (p.nombre.toLowerCase().includes(texto) || p.codigo.toLowerCase().includes(texto))).slice(0, 8)
})
const cantidadValida = (c) => Number.isInteger(Number(c)) && Number(c) > 0
const falta = (i) => cantidadValida(i.cantidad) ? Math.max(0, Number(i.cantidad) - i.producto.cantidad) : 0
const insumosListos = computed(() =>
  insumos.value.every((i) => cantidadValida(i.cantidad) && falta(i) === 0))

function agregarInsumo (producto) {
  insumos.value.push({ producto, cantidad: 1 })
  busquedaInsumo.value = ''
}

function quitarInsumo (indice) {
  insumos.value.splice(indice, 1)
}

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
    monto.value = data.servicio_precio ?? ''
    // Lectura de la ficha clínica: el servidor la deja en la auditoría.
    paciente.value = (await api.get(`/pacientes/${data.paciente}/`)).data
    // Sin el stock se puede registrar igual la atención, sin insumos.
    try {
      stock.value = (await api.get('/inventario/stock/')).data.stock
    } catch (problema) {
      errorDeStock.value = problema.mensaje
    }
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
  montoConError.value = false
  try {
    await api.post('/atenciones/', {
      cita: cita.value.id,
      monto_cobrado: monto.value,
      observaciones_clinicas: observaciones.value.trim(),
      insumos: insumos.value.map((i) => ({ producto: i.producto.id, cantidad: Number(i.cantidad) }))
    })
    router.push({
      name: 'agenda',
      query: { fecha: cita.value.inicio.slice(0, 10), aviso: 'atencion-registrada' }
    })
  } catch (problema) {
    errorAlGuardar.value = problema.mensaje
    montoConError.value = 'monto_cobrado' in (problema.campos ?? {})
    guardando.value = false
    // Otro registro pudo gastar el stock mientras tanto: se refresca para
    // que las filas muestren la existencia real.
    if (problema.codigo === 'stock-insuficiente') await refrescarStock()
  }
}

async function refrescarStock () {
  try {
    stock.value = (await api.get('/inventario/stock/')).data.stock
    for (const i of insumos.value) {
      i.producto = stock.value.find((p) => p.id === i.producto.id) ?? i.producto
    }
  } catch { /* se queda con el que tenía */ }
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
        <div class="campo campo-monto">
          <label for="monto">Monto cobrado (S/) *</label>
          <input
            id="monto"
            v-model="monto"
            type="number"
            step="0.01"
            inputmode="decimal"
            required
            :aria-invalid="montoConError"
            aria-describedby="ayuda-monto"
          >
          <p id="ayuda-monto" class="ayuda">
            Precio del servicio; cámbielo si cobró otro importe.
          </p>
        </div>
        <fieldset class="campo insumos">
          <legend>Insumos consumidos</legend>
          <p v-if="errorDeStock" class="ayuda" role="alert">
            No se pudo leer el stock ({{ errorDeStock }}). Puede registrar la atención sin insumos.
          </p>
          <template v-else>
            <table v-if="insumos.length" class="tabla-insumos">
              <thead>
                <tr>
                  <th scope="col">
                    Producto
                  </th>
                  <th scope="col" class="numero">
                    Stock en sede
                  </th>
                  <th scope="col" class="numero">
                    Cantidad
                  </th>
                  <th scope="col">
                    <span class="solo-lectores">Quitar</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(i, indice) in insumos" :key="i.producto.id" :class="{ 'bajo-minimo': falta(i) > 0 }">
                  <td>
                    <strong>{{ i.producto.nombre }}</strong>
                    <span class="secundario-celda">{{ i.producto.codigo }}</span>
                    <span v-if="falta(i) > 0" class="texto-alerta aviso-stock" role="alert">
                      Faltan {{ falta(i) }} {{ i.producto.unidad }}.
                      <button class="enlace" type="button" @click="productoConsultado = i.producto.id">
                        Ver otras sedes
                      </button>
                    </span>
                  </td>
                  <td class="numero">
                    {{ i.producto.cantidad }} {{ i.producto.unidad }}
                  </td>
                  <td class="numero">
                    <input
                      v-model="i.cantidad"
                      class="cantidad-insumo"
                      type="number"
                      min="1"
                      step="1"
                      inputmode="numeric"
                      :aria-label="`Cantidad de ${i.producto.nombre}`"
                      :aria-invalid="falta(i) > 0 || !cantidadValida(i.cantidad)"
                    >
                  </td>
                  <td class="accion">
                    <button class="enlace" type="button" :aria-label="`Quitar ${i.producto.nombre}`" @click="quitarInsumo(indice)">
                      ×
                    </button>
                  </td>
                </tr>
              </tbody>
            </table>
            <label for="buscar-insumo" class="solo-lectores">Agregar insumo</label>
            <input
              id="buscar-insumo"
              v-model="busquedaInsumo"
              type="search"
              autocomplete="off"
              placeholder="+ Agregar insumo: código o nombre…"
            >
            <ul v-if="sugerenciasInsumo.length" class="sugerencias" aria-label="Productos encontrados">
              <li v-for="p in sugerenciasInsumo" :key="p.id">
                <button type="button" @click="agregarInsumo(p)">
                  <strong>{{ p.nombre }}</strong>
                  <span>{{ p.codigo }} · stock {{ p.cantidad }} {{ p.unidad }}</span>
                </button>
              </li>
            </ul>
            <p class="ayuda">
              Opcional. Se descuentan del stock de la sede al confirmar.
            </p>
          </template>
        </fieldset>

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

        <button type="submit" :disabled="guardando || monto === '' || monto === null || !insumosListos">
          {{ guardando ? 'Guardando…' : 'Confirmar atención' }}
        </button>
      </form>
    </template>
    <DisponibilidadDialogo :producto-id="productoConsultado" @cerrar="productoConsultado = null" />
  </main>
</template>
