<script setup>
// P08 Buscar paciente (CU06). La búsqueda la resuelve el servidor: el
// navegador no recibe el padrón completo, solo las coincidencias.
import { onMounted, ref } from 'vue'
import { api } from '../services/api'

const pacientes = ref([])
const buscar = ref('')
const cargando = ref(false)
const error = ref(null)
const buscado = ref(false)

function edad (fecha) {
  if (!fecha) return '—'
  const nacimiento = new Date(fecha)
  const hoy = new Date()
  let años = hoy.getFullYear() - nacimiento.getFullYear()
  const mes = hoy.getMonth() - nacimiento.getMonth()
  if (mes < 0 || (mes === 0 && hoy.getDate() < nacimiento.getDate())) años -= 1
  return `${años} años`
}

async function cargar () {
  cargando.value = true
  error.value = null
  try {
    const { data } = await api.get('/pacientes/', {
      params: buscar.value ? { buscar: buscar.value } : {}
    })
    pacientes.value = data.results ?? data
  } catch (problema) {
    error.value = problema.mensaje
  } finally {
    cargando.value = false
    buscado.value = true
  }
}

onMounted(cargar)
</script>

<template>
  <main>
    <div class="encabezado encabezado-con-accion">
      <div>
        <h1>Pacientes</h1>
        <p>Busque por nombre, apellido o número de documento.</p>
      </div>
      <router-link class="boton boton-grande" :to="{ name: 'nuevo-paciente' }">
        + Nuevo paciente
      </router-link>
    </div>

    <form class="filtros" @submit.prevent="cargar">
      <div class="campo">
        <label for="buscar">Buscar</label>
        <input id="buscar" v-model="buscar" type="search" placeholder="Quispe, 12345678…">
      </div>
      <button type="submit" :disabled="cargando">
        {{ cargando ? 'Buscando…' : 'Buscar' }}
      </button>
    </form>

    <p v-if="error" role="alert">{{ error }}</p>

    <section class="tarjeta">
      <p v-if="cargando" role="status">Buscando pacientes…</p>
      <p v-else-if="!pacientes.length" class="vacio">
        {{ buscar ? 'Ningún paciente coincide con esa búsqueda.' : 'Todavía no hay pacientes registrados.' }}
        <router-link :to="{ name: 'nuevo-paciente' }">Registrar un paciente nuevo</router-link>
      </p>
      <table v-else>
        <caption>{{ pacientes.length }} paciente(s)</caption>
        <thead>
          <tr>
            <th scope="col">Documento</th>
            <th scope="col">Paciente</th>
            <th scope="col">Edad</th>
            <th scope="col">Teléfono</th>
            <th scope="col">Recordatorios</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="paciente in pacientes" :key="paciente.id">
            <td class="numero">{{ paciente.documento }}</td>
            <td>
              <router-link :to="{ name: 'ficha-paciente', params: { pacienteId: paciente.id } }">
                {{ paciente.apellidos }}, {{ paciente.nombres }}
              </router-link>
            </td>
            <td>{{ edad(paciente.fecha_nacimiento) }}</td>
            <td class="numero">{{ paciente.telefono || '—' }}</td>
            <td>
              <span v-if="paciente.consentimiento_vigente?.acepta_recordatorios"
                    class="etiqueta ATENDIDA">Autorizados</span>
              <span v-else class="etiqueta NO_ASISTIO">No autorizados</span>
            </td>
          </tr>
        </tbody>
      </table>
    </section>
  </main>
</template>
