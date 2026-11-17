<script setup>
// Barra superior: marca, secciones que permite el rol, sede activa y cuenta.
// Las secciones salen de `meta.menu` en router.js, la misma fuente que decide
// los permisos, para que el menú y el guardia de rutas no se contradigan.
import { computed, nextTick, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { SECCIONES } from '../router'
import { useSesion } from '../stores/sesion'
import IconoTrazo from './IconoTrazo.vue'
import MarcaArtemisa from './MarcaArtemisa.vue'
import MenuUsuario from './MenuUsuario.vue'

const sesion = useSesion()
const router = useRouter()
const ruta = useRoute()
const menu = ref(null)

const secciones = computed(() =>
  SECCIONES.filter((s) => s.meta.roles.includes(sesion.usuario?.rol)))

// Una pantalla interna (la ficha, registrar atención) marca su sección.
const esActiva = (seccion) => ruta.name === seccion.name || ruta.meta.seccion === seccion.name

// En pantallas estrechas el menú se desplaza de lado: se trae a la vista la
// sección actual para que siempre se vea dónde se está.
watch(() => ruta.name, async () => {
  await nextTick()
  menu.value?.querySelector('.activa')?.scrollIntoView({ block: 'nearest', inline: 'nearest' })
}, { immediate: true })

// Con una sola sede no hay nada que elegir: se muestra, pero no es un botón.
const puedeCambiarSede = computed(() => sesion.sedes.length > 1)

function cambiarSede () {
  sesion.sedeActivaId = null
  router.push({ name: 'elegir-sede' })
}
</script>

<template>
  <header class="barra">
    <MarcaArtemisa />

    <nav ref="menu" aria-label="Secciones">
      <router-link
        v-for="seccion in secciones"
        :key="seccion.name"
        :to="{ name: seccion.name }"
        :class="{ activa: esActiva(seccion) }"
      >
        {{ seccion.meta.menu }}
      </router-link>
    </nav>

    <div class="derecha">
      <component
        :is="puedeCambiarSede ? 'button' : 'span'"
        v-if="sesion.sedeActiva"
        class="sede"
        v-bind="puedeCambiarSede ? { type: 'button', title: 'Cambiar de sede' } : {}"
        @click="puedeCambiarSede && cambiarSede()"
      >
        <IconoTrazo nombre="sede" :tamano="15" />
        <span class="sede-nombre">{{ sesion.sedeActiva.nombre }}</span>
        <span v-if="puedeCambiarSede" class="solo-lectores">· cambiar de sede</span>
        <IconoTrazo v-if="puedeCambiarSede" nombre="selector" :tamano="13" />
      </component>
      <MenuUsuario />
    </div>
  </header>
</template>

<style scoped>
/* Fija arriba y translúcida: el contenido se adivina debajo al desplazarse. */
.barra {
  position: sticky; top: 0; z-index: 20;
  display: flex; align-items: center; gap: 1.25rem;
  padding: .55rem 1.25rem;
  background: color-mix(in srgb, var(--superficie) 88%, transparent);
  backdrop-filter: saturate(1.4) blur(10px);
  border-bottom: 1px solid var(--borde);
}

/* Nunca parte en dos filas: si no caben las secciones, se desplazan de lado. */
nav {
  flex: 1; min-width: 0;
  display: flex; gap: .15rem;
  overflow-x: auto; scrollbar-width: none;
}
nav::-webkit-scrollbar { display: none; }
nav a {
  flex: none; padding: .45rem .8rem; border-radius: 999px;
  color: var(--tinta-suave); font-weight: 600; font-size: .92rem; text-decoration: none;
  transition: background-color var(--transicion), color var(--transicion);
}
nav a:hover { background: var(--fondo); color: var(--tinta); }
nav a:focus-visible { outline-offset: -2px; }
nav a.activa { background: var(--marca-tenue); color: var(--marca); }

.derecha { flex: none; display: flex; align-items: center; gap: .5rem; }

.sede {
  display: inline-flex; align-items: center; gap: .4rem;
  padding: .35rem .75rem; border-radius: 999px;
  background: var(--fondo); color: var(--tinta); border: 1px solid var(--borde);
  font-size: .88rem; font-weight: 600;
}
button.sede:hover:not(:disabled) { background: var(--marca-tenue); border-color: var(--oficial-claro); }
.sede svg { color: var(--tinta-suave); flex: none; }
.sede-nombre { max-width: 12rem; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

/* En el celular: marca, sede y cuenta en la primera fila (la sede se acorta
   con «…» si no cabe) y las secciones en una fila propia. */
@media (max-width: 860px) {
  .barra { display: grid; grid-template-columns: auto minmax(0, 1fr); gap: .5rem .75rem; padding: .5rem .9rem 0; }
  .derecha { grid-row: 1; grid-column: 2; justify-self: end; min-width: 0; }
  .sede { min-width: 0; }
  .sede-nombre { min-width: 0; max-width: none; }
  nav { grid-row: 2; grid-column: 1 / -1; margin: 0 -.9rem; padding: 0 .9rem .5rem; }
}
</style>
