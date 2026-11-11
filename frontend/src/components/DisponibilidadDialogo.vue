<script setup>
// P14 Disponibilidad entre sedes (CU12), modal sobre P12 (Práctica N.° 7,
// Tabla 14): el mismo producto en todas las sedes del centro, no solo la
// activa, que se señala. Solo informa: no mueve stock entre sedes.
import { ref, watch } from 'vue'
import { api } from '../services/api'

const props = defineProps({ productoId: { type: Number, default: null } })
const emit = defineEmits(['cerrar'])

const dialogo = ref(null)
const datos = ref(null)
const cargando = ref(false)
const error = ref(null)

watch(() => props.productoId, async (id) => {
  if (!dialogo.value) return
  if (id === null) { if (dialogo.value.open) dialogo.value.close(); return }
  datos.value = null
  error.value = null
  cargando.value = true
  dialogo.value.showModal()
  try {
    datos.value = (await api.get('/inventario/disponibilidad/', { params: { producto: id } })).data
  } catch (problema) {
    error.value = problema.mensaje
  } finally {
    cargando.value = false
  }
})
</script>

<template>
  <dialog ref="dialogo" class="dialogo" aria-labelledby="titulo-disponibilidad" @close="emit('cerrar')">
    <form method="dialog" class="dialogo-cabecera">
      <h2 id="titulo-disponibilidad">
        Disponibilidad
      </h2>
      <button class="enlace" type="submit" aria-label="Cerrar">
        ×
      </button>
    </form>
    <div class="dialogo-cuerpo">
      <p v-if="cargando" role="status">
        Consultando las sedes…
      </p>
      <p v-else-if="error" role="alert">
        {{ error }}
      </p>
      <template v-else-if="datos">
        <p class="resumen-atencion">
          <strong>{{ datos.producto.nombre }}</strong> · {{ datos.producto.codigo }}
        </p>
        <table class="disponibilidad">
          <caption class="solo-lectores">
            Stock por sede
          </caption>
          <thead>
            <tr>
              <th scope="col">
                Sede
              </th>
              <th scope="col" class="numero">
                Stock
              </th>
              <th scope="col" class="numero">
                Mín.
              </th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="s in datos.sedes" :key="s.id" :class="{ activa: s.es_activa }">
              <td>{{ s.nombre }}<template v-if="s.es_activa"> (activa)</template></td>
              <td class="numero">
                {{ s.cantidad }} {{ datos.producto.unidad }}
              </td>
              <td class="numero">
                {{ s.minimo }}
              </td>
            </tr>
          </tbody>
        </table>
        <p v-if="datos.sedes.every((s) => s.cantidad === 0)" class="ayuda">
          No hay existencia de este producto en ninguna sede.
        </p>
        <p class="ayuda">
          Solo lectura: esta consulta no mueve stock entre sedes.
        </p>
      </template>
      <div class="dialogo-acciones">
        <button class="secundario" type="button" @click="dialogo.close()">
          Cerrar
        </button>
      </div>
    </div>
  </dialog>
</template>
