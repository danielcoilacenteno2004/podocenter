<script setup>
// Armazón de la aplicación: barra superior y salida del router.
// La barra solo aparece con sesión abierta; el acceso (P01) ocupa la
// pantalla completa.
import { computed } from 'vue'
import { useSesion } from './stores/sesion'
import BarraSuperior from './components/BarraSuperior.vue'

const sesion = useSesion()

const conBarra = computed(() => sesion.autenticado && !sesion.necesitaElegirSede)
</script>

<template>
  <div class="app">
    <a v-if="conBarra" class="saltar" href="#contenido">Saltar al contenido</a>
    <BarraSuperior v-if="conBarra" />

    <!-- Cada pantalla entra con un fundido breve; «out-in» evita que dos
         pantallas convivan un instante y la página dé un salto. -->
    <div id="contenido" class="contenido" tabindex="-1">
      <router-view v-slot="{ Component }">
        <Transition name="pagina" mode="out-in">
          <component :is="Component" />
        </Transition>
      </router-view>
    </div>
  </div>
</template>
