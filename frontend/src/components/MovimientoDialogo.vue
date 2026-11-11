<script setup>
// P13 Registrar movimiento de inventario (CU11), modal sobre P12 (Práctica
// N.° 7, Tabla 13). Tipos elegibles: Entrada, Ajuste (al alta o a la baja) y
// Merma. Que el stock no quede negativo lo decide el servidor; aquí se anticipa
// el resultado («quedará en…») solo como ayuda.
import { computed, nextTick, ref, watch } from 'vue'
import { api } from '../services/api'
import { useSesion } from '../stores/sesion'

const props = defineProps({
  abierto: { type: Boolean, default: false },
  // Filas de P12: { id, codigo, nombre, unidad, cantidad }
  productos: { type: Array, default: () => [] },
  productoInicial: { type: Number, default: null }
})
const emit = defineEmits(['cerrar', 'registrado'])
const sesion = useSesion()

const TIPOS = [['ENTRADA', 'Entrada'], ['AJUSTE', 'Ajuste'], ['MERMA', 'Merma']]
const LIMITE_MOTIVO = 200

const dialogo = ref(null)
const campoBuscar = ref(null)
const busqueda = ref('')
const producto = ref(null)
const tipo = ref('ENTRADA')
const sentido = ref('ALTA')
const cantidad = ref('')
const motivo = ref('')
const confirmandoAjuste = ref(false)
const guardando = ref(false)
const error = ref(null)

const sugerencias = computed(() => {
  const texto = busqueda.value.trim().toLowerCase()
  if (texto.length < 2) return []
  return props.productos.filter((p) =>
    p.nombre.toLowerCase().includes(texto) || p.codigo.toLowerCase().includes(texto)).slice(0, 8)
})

const variacion = computed(() => {
  const n = Number(cantidad.value)
  if (!Number.isInteger(n) || n <= 0) return null
  if (tipo.value === 'ENTRADA') return n
  if (tipo.value === 'MERMA') return -n
  return sentido.value === 'ALTA' ? n : -n
})
const quedara = computed(() =>
  producto.value && variacion.value !== null ? producto.value.cantidad + variacion.value : null)
const motivoObligatorio = computed(() => tipo.value !== 'ENTRADA')
// Primer nivel de la validación de stock (interfaz, servidor y base): no se
// ofrece registrar lo que dejaría la existencia en negativo. El servidor lo
// vuelve a comprobar con la fila bloqueada, y la base con su CHECK.
const dejariaNegativo = computed(() => quedara.value !== null && quedara.value < 0)
const completo = computed(() => Boolean(producto.value && variacion.value !== null &&
  (!motivoObligatorio.value || motivo.value.trim()) && !dejariaNegativo.value))
// Tabla 13: «pide confirmación cuando el ajuste supera el 20 % del stock actual».
const ajusteGrande = computed(() => tipo.value === 'AJUSTE' && producto.value &&
  variacion.value !== null && Math.abs(variacion.value) > 0.2 * producto.value.cantidad)

watch([tipo, sentido, cantidad, producto], () => { confirmandoAjuste.value = false })

watch(() => props.abierto, async (abierto) => {
  if (!dialogo.value) return
  if (!abierto) { if (dialogo.value.open) dialogo.value.close(); return }
  producto.value = props.productos.find((p) => p.id === props.productoInicial) ?? null
  busqueda.value = ''
  tipo.value = 'ENTRADA'
  sentido.value = 'ALTA'
  cantidad.value = ''
  motivo.value = ''
  error.value = null
  confirmandoAjuste.value = false
  dialogo.value.showModal()
  await nextTick()
  if (!producto.value) campoBuscar.value?.focus()
})

function elegir (p) {
  producto.value = p
  busqueda.value = ''
}

async function registrar () {
  if (ajusteGrande.value && !confirmandoAjuste.value) {
    confirmandoAjuste.value = true
    return
  }
  guardando.value = true
  error.value = null
  try {
    const { data } = await api.post('/inventario/movimientos/', {
      producto: producto.value.id,
      tipo: tipo.value,
      sentido: tipo.value === 'AJUSTE' ? sentido.value : undefined,
      cantidad: Number(cantidad.value),
      motivo: motivo.value.trim()
    })
    emit('registrado', { producto: producto.value, movimiento: data })
  } catch (problema) {
    error.value = problema.mensaje
    confirmandoAjuste.value = false
  } finally {
    guardando.value = false
  }
}
</script>

<template>
  <dialog ref="dialogo" class="dialogo" aria-labelledby="titulo-movimiento" @close="emit('cerrar')">
    <form method="dialog" class="dialogo-cabecera">
      <h2 id="titulo-movimiento">
        Registrar movimiento de inventario
      </h2>
      <button class="enlace" type="submit" aria-label="Cerrar">
        ×
      </button>
    </form>

    <form class="dialogo-cuerpo" @submit.prevent="registrar">
      <div class="campo">
        <label for="mov-producto">Producto *</label>
        <div v-if="producto" class="elegido">
          <span><strong>{{ producto.nombre }}</strong> · {{ producto.codigo }}</span>
          <button class="enlace" type="button" @click="producto = null">
            Cambiar
          </button>
        </div>
        <template v-else>
          <input
            id="mov-producto"
            ref="campoBuscar"
            v-model="busqueda"
            type="search"
            autocomplete="off"
            placeholder="Código o nombre (desde 2 caracteres)…"
          >
          <ul v-if="sugerencias.length" class="sugerencias" aria-label="Productos encontrados">
            <li v-for="p in sugerencias" :key="p.id">
              <button type="button" @click="elegir(p)">
                <strong>{{ p.nombre }}</strong>
                <span>{{ p.codigo }} · stock {{ p.cantidad }}</span>
              </button>
            </li>
          </ul>
        </template>
      </div>

      <div class="fila-campos">
        <div class="campo">
          <label for="mov-tipo">Tipo *</label>
          <select id="mov-tipo" v-model="tipo">
            <option v-for="[valor, etiqueta] in TIPOS" :key="valor" :value="valor">
              {{ etiqueta }}
            </option>
          </select>
        </div>
        <div class="campo">
          <label for="mov-cantidad">Cantidad *</label>
          <input id="mov-cantidad" v-model="cantidad" type="number" min="1" step="1" inputmode="numeric" required>
        </div>
      </div>

      <fieldset v-if="tipo === 'AJUSTE'" class="campo opciones">
        <legend>Dirección del ajuste *</legend>
        <label><input v-model="sentido" type="radio" name="sentido" value="ALTA"> Al alta (hay más de lo registrado)</label>
        <label><input v-model="sentido" type="radio" name="sentido" value="BAJA"> A la baja (hay menos de lo registrado)</label>
      </fieldset>

      <div class="campo">
        <label for="mov-motivo">Motivo{{ motivoObligatorio ? ' *' : '' }}</label>
        <input id="mov-motivo" v-model="motivo" :maxlength="LIMITE_MOTIVO" :required="motivoObligatorio" placeholder="Compra a proveedor, conteo físico, tubo vencido…">
      </div>

      <p v-if="producto" class="ayuda" role="status">
        Stock actual en {{ sesion.sedeActiva?.nombre }}: {{ producto.cantidad }} {{ producto.unidad }}
        <template v-if="quedara !== null">
          → quedará en <strong :class="{ 'texto-alerta': quedara < 0 }">{{ quedara }}</strong>
        </template>
      </p>
      <p v-if="dejariaNegativo" class="texto-alerta ayuda">
        La cantidad supera el stock disponible en la sede.
      </p>

      <p v-if="confirmandoAjuste" class="aviso-ajuste" role="alert">
        El ajuste supera el 20 % del stock actual. Pulse «Confirmar ajuste» si el conteo es correcto.
      </p>
      <p v-if="error" role="alert">
        {{ error }}
      </p>

      <div class="dialogo-acciones">
        <button class="secundario" type="button" @click="dialogo.close()">
          Cancelar
        </button>
        <button type="submit" :disabled="!completo || guardando">
          {{ guardando ? 'Registrando…' : (confirmandoAjuste ? 'Confirmar ajuste' : 'Registrar') }}
        </button>
      </div>
    </form>
  </dialog>
</template>
