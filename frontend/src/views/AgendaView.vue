<script setup>
// P05 Agenda de citas. Solo pinta lo que devuelve la API: la regla de
// solapamiento la decide el servidor, nunca el navegador.
import { onMounted, ref } from 'vue'
import { api } from '../services/api'

const citas = ref([])
const fecha = ref(new Date().toISOString().slice(0, 10))
const error = ref(null)
const cargando = ref(false)

async function cargarAgenda () {
  cargando.value = true
  error.value = null
  try {
    const { data } = await api.get('/citas/agenda/', { params: { fecha: fecha.value } })
    citas.value = data.citas
  } catch (problema) {
    error.value = problema.mensaje
  } finally {
    cargando.value = false
  }
}

onMounted(cargarAgenda)
</script>

<template>
  <section aria-labelledby="titulo-agenda">
    <h1 id="titulo-agenda">Agenda de citas</h1>
    <label for="fecha">Fecha</label>
    <input id="fecha" v-model="fecha" type="date" @change="cargarAgenda">

    <p v-if="cargando" role="status">Cargando la agenda…</p>
    <p v-else-if="error" role="alert">{{ error }}</p>

    <table v-else>
      <caption>Citas del día</caption>
      <thead>
        <tr><th scope="col">Hora</th><th scope="col">Paciente</th><th scope="col">Servicio</th><th scope="col">Estado</th></tr>
      </thead>
      <tbody>
        <tr v-for="cita in citas" :key="cita.id">
          <td>{{ new Date(cita.inicio).toLocaleTimeString('es-PE', { hour: '2-digit', minute: '2-digit' }) }}</td>
          <td>{{ cita.paciente_nombre }}</td>
          <td>{{ cita.servicio_nombre }}</td>
          <td>{{ cita.estado }}</td>
        </tr>
        <tr v-if="citas.length === 0"><td colspan="4">No hay citas programadas para esta fecha.</td></tr>
      </tbody>
    </table>
  </section>
</template>
