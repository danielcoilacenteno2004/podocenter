<script setup>
// Armazón de la aplicación: barra de navegación y salida del router.
// La barra solo aparece con sesión abierta; el acceso (P01) ocupa la
// pantalla completa.
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { useSesion } from './stores/sesion'
import MarcaArtemisa from './components/MarcaArtemisa.vue'

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
      <MarcaArtemisa />

      <nav aria-label="Secciones">
        <router-link v-if="sesion.esAdministradoraDePlataforma" :to="{ name: 'centros' }">Centros clientes</router-link>
        <template v-else>
          <router-link :to="{ name: 'panel' }">Panel del día</router-link>
          <router-link :to="{ name: 'agenda' }">Agenda</router-link>
          <router-link :to="{ name: 'pacientes' }">Pacientes</router-link>
          <router-link :to="{ name: 'inventario' }">Inventario</router-link>
          <router-link :to="{ name: 'registro-diario' }">Registro diario</router-link>
        </template>
        <template v-if="sesion.esAdministradoraDelCentro">
          <router-link :to="{ name: 'usuarios' }">Usuarios</router-link>
          <router-link :to="{ name: 'sedes' }">Sedes</router-link>
          <router-link :to="{ name: 'servicios' }">Servicios</router-link>
        </template>
      </nav>

      <div class="derecha">
        <button v-if="sesion.sedes.length > 1" class="enlace" type="button" @click="cambiarSede">
          {{ sesion.sedeActiva?.nombre ?? 'Elegir sede' }} · cambiar
        </button>
        <span v-else-if="sesion.sedeActiva" class="identidad">
          <span>{{ sesion.sedeActiva.nombre }}</span>
        </span>
        <router-link class="identidad" :to="{ name: 'perfil' }" title="Mi perfil y seguridad">
          <strong>{{ sesion.usuario?.nombre_completo }}</strong>
          <span>{{ sesion.usuario?.rol_descripcion }}</span>
        </router-link>
        <button class="secundario" type="button" @click="salir">Salir</button>
      </div>
    </header>

    <router-view />
  </div>
</template>
