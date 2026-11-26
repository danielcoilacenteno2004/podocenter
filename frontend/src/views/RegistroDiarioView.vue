<script setup>
// P16 Registro diario (CU13, RF14), según el wireframe de la Práctica N.° 7:
// para la sede activa y la fecha elegida, cada atención con lo que se cobró
// y el total del día. El servidor lo calcula desde las atenciones; no hay una
// tabla de ingresos aparte que pueda descuadrar (Informe, Tabla 39).
//
// Del wireframe no se construyen las «ventas» (salen del inventario, que no
// existe). «Exportar» (P22, RF16) descarga el día elegido, o un rango de
// hasta 31 días, en PDF o Excel; el servidor arma el archivo con la misma
// consulta de esta pantalla, así que el total es el mismo.
import { onMounted, ref, watch } from 'vue'
import { api, descargarArchivo } from '../services/api'
import { useSesion } from '../stores/sesion'
import TarjetaSeccion from '../components/TarjetaSeccion.vue'

const sesion = useSesion()

const fecha = ref(new Date().toLocaleDateString('en-CA'))
const registro = ref(null)
const cargando = ref(false)
const error = ref(null)

const hora = (valor) => new Date(valor).toLocaleTimeString('es-PE', { hour: '2-digit', minute: '2-digit' })
const soles = (valor) => (valor === null || valor === undefined ? '—' : `S/ ${Number(valor).toFixed(2)}`)

// Como en la agenda: si se cambia la fecha antes de que llegue la respuesta
// anterior, solo se pinta la última pedida.
let turno = 0
async function cargar () {
  const mio = ++turno
  cargando.value = true
  error.value = null
  try {
    const { data } = await api.get('/reportes/registro-diario/', { params: { fecha: fecha.value } })
    if (mio === turno) registro.value = data
  } catch (problema) {
    if (mio === turno) { error.value = problema.mensaje; registro.value = null }
  } finally {
    if (mio === turno) cargando.value = false
  }
}

watch(fecha, cargar)
onMounted(cargar)

// Exportación (RF16): por omisión, el día que se está viendo.
const variosDias = ref(false)
const hasta = ref(fecha.value)
const exportando = ref(null)
const errorExportar = ref(null)
watch(fecha, (valor) => { if (!variosDias.value || hasta.value < valor) hasta.value = valor })

async function exportar (formato) {
  exportando.value = formato
  errorExportar.value = null
  try {
    const params = variosDias.value
      ? { formato, desde: fecha.value, hasta: hasta.value }
      : { formato, fecha: fecha.value }
    await descargarArchivo('/reportes/registro-diario/exportar/', params)
  } catch (problema) {
    errorExportar.value = problema.mensaje
  } finally {
    exportando.value = null
  }
}
</script>

<template>
  <main>
    <div class="encabezado">
      <h1>Registro diario</h1>
      <p v-if="sesion.sedeActiva">
        {{ sesion.sedeActiva.nombre }}
      </p>
    </div>

    <form class="filtros" aria-label="Día del registro" @submit.prevent>
      <div class="campo">
        <label for="fecha-registro">{{ variosDias ? 'Desde' : 'Fecha' }}</label>
        <input id="fecha-registro" v-model="fecha" type="date">
      </div>
      <div v-if="variosDias" class="campo">
        <label for="fecha-hasta">Hasta (para exportar)</label>
        <input id="fecha-hasta" v-model="hasta" type="date" :min="fecha">
      </div>
      <label class="casilla">
        <input v-model="variosDias" type="checkbox">
        Exportar varios días
      </label>
      <div class="acciones-exportar">
        <button type="button" class="secundario" :disabled="exportando !== null"
                :aria-busy="exportando === 'pdf'" @click="exportar('pdf')">
          {{ exportando === 'pdf' ? 'Generando…' : 'Exportar PDF' }}
        </button>
        <button type="button" class="secundario" :disabled="exportando !== null"
                :aria-busy="exportando === 'xlsx'" @click="exportar('xlsx')">
          {{ exportando === 'xlsx' ? 'Generando…' : 'Exportar Excel' }}
        </button>
      </div>
    </form>

    <p v-if="errorExportar" role="alert">
      {{ errorExportar }}
    </p>
    <p v-if="error" role="alert">
      {{ error }}
    </p>

    <TarjetaSeccion>
      <p v-if="cargando && !registro" role="status">
        Cargando el registro…
      </p>
      <template v-else-if="registro">
        <p v-if="!registro.atenciones.length" class="vacio">
          No hay atenciones registradas en esta sede para ese día.
        </p>
        <table v-else class="registro-diario">
          <caption>Atenciones del día, en orden de registro</caption>
          <thead>
            <tr>
              <th scope="col">
                Hora
              </th>
              <th scope="col">
                Paciente
              </th>
              <th scope="col">
                Concepto
              </th>
              <th scope="col">
                Profesional
              </th>
              <th scope="col" class="monto">
                Monto
              </th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="a in registro.atenciones" :key="a.id">
              <td class="numero">
                {{ hora(a.registrada_en) }}
              </td>
              <td>{{ a.paciente_nombre }}</td>
              <td>{{ a.servicio_nombre }}</td>
              <td>{{ a.profesional_nombre }}</td>
              <td class="numero monto">
                {{ soles(a.monto_cobrado) }}
              </td>
            </tr>
          </tbody>
          <tfoot>
            <tr>
              <th scope="row" colspan="4">
                {{ registro.cantidad }} atención(es)
              </th>
              <td class="numero monto total">
                {{ soles(registro.total) }}
              </td>
            </tr>
          </tfoot>
        </table>
      </template>
      <template v-if="registro?.sin_monto" #pie>
        {{ registro.sin_monto }} atención(es) se registraron antes de que existiera el monto
        cobrado: aparecen con «—» y no suman al total.
      </template>
    </TarjetaSeccion>
  </main>
</template>

<style scoped>
.acciones-exportar { display: flex; gap: .5rem; flex-wrap: wrap; margin-left: auto; }
.filtros .casilla { margin: 0; padding: .55rem 0; }
</style>
