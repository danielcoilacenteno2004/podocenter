<script setup>
// P03 Elección de sede. Solo se muestra cuando el usuario tiene más de una
// asignada; con una sola, el sistema la fija sin preguntar (CC-04).
import { useRouter } from 'vue-router'
import { useSesion } from '../stores/sesion'

const sesion = useSesion()
const router = useRouter()

function elegir (sedeId) {
  sesion.elegirSede(sedeId)
  router.push({ name: 'panel' })
}
</script>

<template>
  <div class="acceso">
    <section class="tarjeta" aria-labelledby="titulo-sede">
      <h1 id="titulo-sede">¿En qué sede trabajará hoy?</h1>
      <p style="color:var(--tinta-suave);margin:.25rem 0 1.25rem">
        Todo lo que registre quedará asociado a esta sede. Puede cambiarla
        cuando quiera desde la barra superior.
      </p>

      <ul class="sedes">
        <li v-for="sede in sesion.sedes" :key="sede.id">
          <button type="button" @click="elegir(sede.id)">
            <strong>{{ sede.nombre }}</strong>
            <span>{{ sede.direccion }}</span>
          </button>
        </li>
      </ul>
    </section>
  </div>
</template>
