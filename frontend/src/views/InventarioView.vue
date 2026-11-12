<script setup>
// P12 Inventario de la sede (CU11, RF11, RF13 ajustado por CC-12), según el
// wireframe y la Tabla 12 de la Práctica N.° 7. Abre P13 para registrar un
// movimiento y P14 para ver el mismo producto en las demás sedes.
//
// RF13 ajustado: no hay alerta automática; el stock bajo el mínimo se ve
// aquí, resaltado por texto y fondo, y se puede filtrar.
//
// La administradora edita el mínimo en línea (CU05; se guarda al salir del
// campo) y mantiene el catálogo de productos. La salida por consumo la
// genera P11 al registrar una atención con sus insumos.
import { computed, onMounted, ref } from 'vue'
import DisponibilidadDialogo from '../components/DisponibilidadDialogo.vue'
import MovimientoDialogo from '../components/MovimientoDialogo.vue'
import ProductoDialogo from '../components/ProductoDialogo.vue'
import { api } from '../services/api'
import { useSesion } from '../stores/sesion'

const sesion = useSesion()
const esAdministradora = computed(() => sesion.esAdministradoraDelCentro)

const productoAbierto = ref(false)
const productoEditado = ref(null)
const errorMinimo = ref({})      // id del producto → mensaje del servidor

function abrirProducto (fila = null) {
  productoEditado.value = fila
  productoAbierto.value = true
}

async function productoGuardado ({ producto, nuevo }) {
  productoAbierto.value = false
  aviso.value = nuevo
    ? `${producto.nombre} creado. Registre una entrada para darle stock.`
    : `${producto.nombre} actualizado.`
  await cargar()
}

// Los desactivados no salen en la tabla; se listan aparte para poder
// reactivarlos.
const desactivados = ref([])
async function cargarDesactivados () {
  if (!esAdministradora.value) return
  try {
    const { data } = await api.get('/inventario/productos/', { params: { inactivos: 1 } })
    desactivados.value = data.productos.filter((p) => !p.esta_activo)
  } catch { desactivados.value = [] }
}

async function reactivar (producto) {
  try {
    await api.patch(`/inventario/productos/${producto.id}/`, { esta_activo: true })
    aviso.value = `${producto.nombre} vuelve a estar activo.`
    await cargar()
  } catch (problema) {
    error.value = problema.mensaje
  }
}

async function guardarMinimo (fila, valor) {
  const minimo = Number(valor)
  if (valor === '' || minimo === fila.minimo) return
  errorMinimo.value = { ...errorMinimo.value, [fila.id]: null }
  try {
    const { data } = await api.patch(`/inventario/stock/${fila.id}/`, { minimo })
    fila.minimo = data.minimo
    fila.bajo_minimo = data.bajo_minimo
  } catch (problema) {
    errorMinimo.value = { ...errorMinimo.value, [fila.id]: problema.mensaje }
  }
}

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
  await cargarDesactivados()
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
      <div class="acciones-fila">
        <button v-if="esAdministradora" class="secundario" type="button" @click="abrirProducto()">
          + Producto
        </button>
        <button type="button" :disabled="!stock.length" @click="abrirMovimiento()">
          + Movimiento
        </button>
      </div>
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
              <input
                v-if="esAdministradora"
                class="minimo-en-linea"
                type="number"
                min="0"
                step="1"
                inputmode="numeric"
                :value="f.minimo"
                :aria-label="`Mínimo de ${f.nombre}`"
                :aria-invalid="Boolean(errorMinimo[f.id])"
                @change="guardarMinimo(f, $event.target.value)"
              >
              <template v-else>
                {{ f.minimo }}
              </template>
              <span v-if="errorMinimo[f.id]" class="texto-alerta aviso-stock" role="alert">{{ errorMinimo[f.id] }}</span>
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
                <button v-if="esAdministradora" class="secundario boton-fila" type="button" :aria-label="`Editar el producto ${f.nombre}`" @click="abrirProducto(f)">
                  Editar
                </button>
              </div>
            </td>
          </tr>
        </tbody>
      </table>
      <details v-if="desactivados.length" class="desactivados">
        <summary>Productos desactivados ({{ desactivados.length }})</summary>
        <ul>
          <li v-for="p in desactivados" :key="p.id">
            {{ p.nombre }} · {{ p.codigo }}
            <button class="enlace" type="button" @click="reactivar(p)">
              Reactivar
            </button>
          </li>
        </ul>
      </details>
      <p class="ayuda nota-pendiente">
        Además de las entradas, ajustes y mermas, el stock baja solo con los insumos que se
        registran en cada atención.
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
    <ProductoDialogo
      :abierto="productoAbierto"
      :producto="productoEditado"
      @cerrar="productoAbierto = false"
      @guardado="productoGuardado"
    />
  </main>
</template>
