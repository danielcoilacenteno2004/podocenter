<script setup>
// Armazón de la aplicación: barra de navegación y salida del router.
// La barra solo aparece con sesión abierta; el acceso (P01) ocupa la
// pantalla completa.
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { useSesion } from './stores/sesion'

const sesion = useSesion()
const router = useRouter()

const conBarra = computed(() => sesion.autenticado && !sesion.necesitaElegirSede)

async function salir () {
  await sesion.cerrarSesion()
  router.push({ name: 'login' })
}

function cambiarSede () {
  sesion.sedeActivaId = null
  router.push({ name: 'elegir-sede' })
}
</script>

<template>
  <div class="app">
    <header v-if="conBarra" class="barra">
      <span class="marca">
        <svg width="22" height="22" viewBox="0 0 24 24" aria-hidden="true">
          <path d="M7 3.5c1.7 0 2.8 1.6 2.8 3.6S8.7 10.7 7 10.7 4.2 9.1 4.2 7.1 5.3 3.5 7 3.5Z" fill="#0f6f6a"/>
          <path d="M12.6 4.6c1.3 0 2.1 1.2 2.1 2.7s-.8 2.7-2.1 2.7-2.1-1.2-2.1-2.7.8-2.7 2.1-2.7ZM16.9 7c1 0 1.7 1 1.7 2.2s-.7 2.2-1.7 2.2-1.7-1-1.7-2.2.7-2.2 1.7-2.2Z" fill="#0f6f6a" opacity=".75"/>
          <path d="M6.5 12.4c2.7 0 4.6 1 6.9 2.3 2 1.1 3.2 2.2 3.2 3.8 0 1.6-1.4 2.6-3.3 2.6-1.6 0-2.5-.5-4.2-.5-1.5 0-2.4.4-3.6.4-1.7 0-3-1-3-2.9 0-2 1.3-3.4 2.1-4.6.5-.7 1-1.1 1.9-1.1Z" fill="#0f6f6a"/>
        </svg>
        PodoCenter
      </span>

      <nav aria-label="Secciones">
        <router-link :to="{ name: 'panel' }">Panel del día</router-link>
        <router-link :to="{ name: 'agenda' }">Agenda</router-link>
        <router-link :to="{ name: 'pacientes' }">Pacientes</router-link>
        <template v-if="sesion.esAdministradoraDelCentro">
          <router-link :to="{ name: 'usuarios' }">Usuarios</router-link>
          <router-link :to="{ name: 'sedes' }">Sedes</router-link>
        </template>
      </nav>

      <div class="derecha">
        <button v-if="sesion.sedes.length > 1" class="enlace" type="button" @click="cambiarSede">
          {{ sesion.sedeActiva?.nombre ?? 'Elegir sede' }} · cambiar
        </button>
        <span v-else-if="sesion.sedeActiva" class="identidad">
          <span>{{ sesion.sedeActiva.nombre }}</span>
        </span>
        <span class="identidad">
          <strong>{{ sesion.usuario?.nombre_completo }}</strong>
          <span>{{ sesion.usuario?.rol_descripcion }}</span>
        </span>
        <button class="secundario" type="button" @click="salir">Salir</button>
      </div>
    </header>

    <router-view />
  </div>
</template>
