<script setup>
// Alta y edición de un producto del catálogo del centro, sobre P12. No está
// entre las 29 pantallas de la Práctica N.° 7: se añadió porque sin él un
// centro nuevo no tenía con qué llenar su inventario. Solo la administradora.
// El código repetido y los campos vacíos los decide el servidor.
import { nextTick, ref, watch } from 'vue'
import { api } from '../services/api'

const props = defineProps({
  abierto: { type: Boolean, default: false },
  // null = alta; si no, la fila de P12 que se edita
  producto: { type: Object, default: null }
})
const emit = defineEmits(['cerrar', 'guardado'])

const dialogo = ref(null)
const primerCampo = ref(null)
const formulario = ref({})
const guardando = ref(false)
const error = ref(null)

watch(() => props.abierto, async (abierto) => {
  if (!dialogo.value) return
  if (!abierto) { if (dialogo.value.open) dialogo.value.close(); return }
  const p = props.producto
  formulario.value = p
    ? { codigo: p.codigo, nombre: p.nombre, unidad: p.unidad, esta_activo: p.esta_activo !== false }
    : { codigo: '', nombre: '', unidad: 'unidad', esta_activo: true }
  error.value = null
  dialogo.value.showModal()
  await nextTick()
  primerCampo.value?.focus()
})

async function guardar () {
  guardando.value = true
  error.value = null
  try {
    const { data } = props.producto
      ? await api.patch(`/inventario/productos/${props.producto.id}/`, formulario.value)
      : await api.post('/inventario/productos/', formulario.value)
    emit('guardado', { producto: data, nuevo: !props.producto })
  } catch (problema) {
    error.value = problema.mensaje
  } finally {
    guardando.value = false
  }
}
</script>

<template>
  <dialog ref="dialogo" class="dialogo" aria-labelledby="titulo-producto" @close="emit('cerrar')">
    <form method="dialog" class="dialogo-cabecera">
      <h2 id="titulo-producto">
        {{ producto ? `Editar ${producto.nombre}` : 'Nuevo producto' }}
      </h2>
      <button class="enlace" type="submit" aria-label="Cerrar">
        ×
      </button>
    </form>
    <form class="dialogo-cuerpo" @submit.prevent="guardar">
      <div class="fila-campos">
        <div class="campo">
          <label for="prod-codigo">Código *</label>
          <input id="prod-codigo" ref="primerCampo" v-model="formulario.codigo" maxlength="20" required>
        </div>
        <div class="campo">
          <label for="prod-unidad">Unidad *</label>
          <input id="prod-unidad" v-model="formulario.unidad" maxlength="20" required placeholder="unidad, caja, paquete…">
        </div>
      </div>
      <div class="campo">
        <label for="prod-nombre">Nombre *</label>
        <input id="prod-nombre" v-model="formulario.nombre" maxlength="120" required>
      </div>
      <label v-if="producto" class="casilla">
        <input v-model="formulario.esta_activo" type="checkbox">
        <span><strong>Producto activo</strong>
          <span class="ayuda">Desactivarlo lo quita del inventario y de las atenciones; conserva sus movimientos.</span></span>
      </label>
      <p v-else class="ayuda">
        Nace con stock 0 en todas las sedes; la existencia entra con un movimiento de entrada.
      </p>
      <p v-if="error" role="alert">
        {{ error }}
      </p>
      <div class="dialogo-acciones">
        <button class="secundario" type="button" @click="dialogo.close()">
          Cancelar
        </button>
        <button type="submit" :disabled="guardando || !formulario.codigo?.trim() || !formulario.nombre?.trim() || !formulario.unidad?.trim()">
          {{ guardando ? 'Guardando…' : 'Guardar' }}
        </button>
      </div>
    </form>
  </dialog>
</template>
