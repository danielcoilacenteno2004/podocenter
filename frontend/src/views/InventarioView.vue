<script setup>
// P12 Inventario de la sede (CU11, RF11, RF13 ajustado por CC-12), según el
// wireframe y la Tabla 12 de la Práctica N.° 7. Abre P13 para registrar un
// movimiento y P14 para ver el mismo producto en las demás sedes.
//
// RF13 ajustado: no hay alerta automática; el stock bajo el mínimo se ve
// aquí, resaltado por texto y fondo, y se puede filtrar.
//
// No construido aún: editar el mínimo en línea (CU05) y la salida automática
// por consumo en una atención, que necesita que P11 registre insumos.
import { computed, onMounted, ref } from 'vue'
import DisponibilidadDialogo from '../components/DisponibilidadDialogo.vue'
import MovimientoDialogo from '../components/MovimientoDialogo.vue'
import { api } from '../services/api'
import { useSesion } from '../stores/sesion'

const sesion = useSesion()

const stock = ref([])
const cargando = ref(false)
const error = ref(null)
const aviso = ref(null)
const buscar = ref('')
const soloBajoMinimo = ref(false)

const movimientoAbierto = ref(false)
const productoDelMovimiento = ref(null)
const productoConsultado = ref(null)

// Filtra sin recargar, desde 2 caracteres (Tabla 12).
const filas = computed(() => {
  const texto = buscar.value.trim().toLowerCase()
  return stock.value.filter((f) =>
    (!soloBajoMinimo.value || f.bajo_minimo) &&
    (texto.length < 2 || f.nombre.toLowerCase().includes(texto) || f.codigo.toLowerCase().includes(texto)))
})
const bajoMinimo = computed(() => stock.value.filter((f) => f.bajo_minimo).length)

async function cargar () {
  cargando.value = true
  error.value = null
  try {
    stock.value = (await api.get('/inventario/stock/')).data.stock
  } catch (problema) {
    error.value = problema.mensaje
  } finally {
    cargando.value = false
  }
}

function abrirMovimiento (productoId = null) {
  productoDelMovimiento.value = productoId
  movimientoAbierto.value = true
}

async function movimientoRegistrado ({ producto, movimiento }) {
  movimientoAbierto.value = false
  const signo = movimiento.cantidad > 0 ? '+' : ''
  aviso.value = `${producto.nombre}: ${signo}${movimiento.cantidad} ${producto.unidad}. ` +
    `Stock en ${sesion.sedeActiva?.nombre}: ${movimiento.existencia_resultante}.`
  await cargar()
}

onMounted(cargar)
</script>

<template>
  <main>
    <div class="encabezado encabezado-con-accion">
      <div>
        <h1>Inventario — {{ sesion.sedeActiva?.nombre }}</h1>
        <p>El stock solo cambia por un movimiento; nunca se edita a mano.</p>
      </div>
      <button type="button" :disabled="!stock.length" @click="abrirMovimiento()">
        + Movimiento
      </button>
    </div>

    <form class="filtros" aria-label="Filtros del inventario" @submit.prevent>
      <div class="campo">
        <label for="inv-buscar">Buscar</label>
        <input id="inv-buscar" v-model="buscar" type="search" placeholder="Código o nombre…">
      </div>
      <label class="casilla filtro-casilla">
        <input v-model="soloBajoMinimo" type="checkbox">
        <span>Solo bajo el mínimo<template v-if="bajoMinimo"> ({{ bajoMinimo }})</template></span>
      </label>
    </form>

    <p v-if="error" role="alert">
      {{ error }}
    </p>
    <p v-if="aviso" class="aviso-ok" role="status">
      {{ aviso }}
    </p>

    <section class="tarjeta">
      <p v-if="cargando && !stock.length" role="status">
        Cargando el inventario…
      </p>
      <p v-else-if="!filas.length" class="vacio">
        {{ stock.length ? 'Ningún producto coincide con el filtro.' : 'El centro todavía no tiene productos.' }}
      </p>
      <table v-else class="administracion inventario">
        <caption>{{ filas.length }} de {{ stock.length }} producto(s)</caption>
        <thead>
          <tr>
            <th scope="col">
              Código
            </th>
            <th scope="col">
              Producto
            </th>
            <th scope="col">
              Unid.
            </th>
            <th scope="col" class="numero">
              Stock
            </th>
            <th scope="col" class="numero">
              Mínimo
            </th>
            <th scope="col">
              Estado
            </th>
            <th scope="col">
              <span class="solo-lectores">Acciones</span>
            </th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="f in filas" :key="f.id" :class="{ 'bajo-minimo': f.bajo_minimo }">
            <td class="numero">
              {{ f.codigo }}
            </td>
            <td>{{ f.nombre }}</td>
            <td>{{ f.unidad }}</td>
            <td class="numero">
              {{ f.cantidad }}
            </td>
            <td class="numero">
              {{ f.minimo }}
            </td>
            <td>
              <strong v-if="f.bajo_minimo">Bajo mín.</strong>
              <span v-else>Normal</span>
            </td>
            <td class="accion">
              <div class="acciones-fila">
                <button class="secundario boton-fila" type="button" :aria-label="`Registrar movimiento de ${f.nombre}`" @click="abrirMovimiento(f.id)">
                  Movimiento
                </button>
                <button class="secundario boton-fila" type="button" :aria-label="`Ver disponibilidad de ${f.nombre}`" @click="productoConsultado = f.id">
                  Ver disponibilidad
                </button>
              </div>
            </td>
          </tr>
        </tbody>
      </table>
      <p class="ayuda nota-pendiente">
        La salida automática por consumo en una atención todavía no existe: P11 aún no registra
        insumos. Por ahora el stock cambia solo con entradas, ajustes y mermas.
      </p>
    </section>

    <MovimientoDialogo
      :abierto="movimientoAbierto"
      :productos="stock"
      :producto-inicial="productoDelMovimiento"
      @cerrar="movimientoAbierto = false"
      @registrado="movimientoRegistrado"
    />
    <DisponibilidadDialogo :producto-id="productoConsultado" @cerrar="productoConsultado = null" />
  </main>
</template>
