<script setup>
// Menú de la cuenta: quién está conectado, acceso a «Mi perfil» (P20) y salir.
// Es un botón que despliega un panel (aria-expanded), no un role="menu": así
// no exige navegar con flechas y los lectores de pantalla lo anuncian bien.
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useSesion } from '../stores/sesion'
import IconoTrazo from './IconoTrazo.vue'

const sesion = useSesion()
const router = useRouter()
const ruta = useRoute()

const abierto = ref(false)
const raiz = ref(null)
const disparador = ref(null)

const nombre = computed(() => sesion.usuario?.nombre_completo ?? '')
const iniciales = computed(() => nombre.value
  .split(/\s+/).filter(Boolean).slice(0, 2)
  .map((palabra) => palabra[0].toUpperCase()).join(''))

function cerrar ({ devolverFoco = false } = {}) {
  abierto.value = false
  if (devolverFoco) disparador.value?.focus()
}

// Se cierra al pulsar fuera, con Escape (devolviendo el foco al botón) y al
// cambiar de pantalla.
function alPulsarFuera (evento) {
  if (abierto.value && !raiz.value?.contains(evento.target)) cerrar()
}
function alPulsarTecla (evento) {
  if (evento.key === 'Escape' && abierto.value) cerrar({ devolverFoco: true })
}
onMounted(() => {
  document.addEventListener('pointerdown', alPulsarFuera)
  document.addEventListener('keydown', alPulsarTecla)
})
onBeforeUnmount(() => {
  document.removeEventListener('pointerdown', alPulsarFuera)
  document.removeEventListener('keydown', alPulsarTecla)
})
watch(() => ruta.fullPath, () => cerrar())

async function salir () {
  await sesion.cerrarSesion()
  router.push({ name: 'login' })
}
</script>

<template>
  <div ref="raiz" class="menu-usuario">
    <button
      ref="disparador"
      type="button"
      class="disparador"
      :aria-expanded="abierto"
      aria-controls="menu-cuenta"
      :aria-label="`Cuenta de ${nombre}`"
      @click="abierto = !abierto"
    >
      <span class="avatar" aria-hidden="true">{{ iniciales }}</span>
      <span class="quien">
        <strong>{{ nombre }}</strong>
        <span>{{ sesion.usuario?.rol_descripcion }}</span>
      </span>
      <IconoTrazo class="flecha" nombre="abajo" :tamano="14" />
    </button>

    <Transition name="desplegar">
      <div v-if="abierto" id="menu-cuenta" class="panel">
        <p class="cabecera">
          <strong>{{ nombre }}</strong>
          <span>{{ sesion.usuario?.correo }}</span>
          <span>{{ sesion.usuario?.rol_descripcion }}</span>
        </p>
        <router-link class="opcion" :to="{ name: 'perfil' }">
          <IconoTrazo nombre="usuario" :tamano="16" />
          Mi perfil y seguridad
        </router-link>
        <button type="button" class="opcion salir" @click="salir">
          <IconoTrazo nombre="salir" :tamano="16" />
          Salir
        </button>
      </div>
    </Transition>
  </div>
</template>

<style scoped>
.menu-usuario { position: relative; }

.disparador {
  display: flex; align-items: center; gap: .55rem;
  padding: .2rem .55rem .2rem .2rem; border-radius: 999px;
  background: transparent; border: 1px solid transparent; color: var(--tinta); font-weight: 400;
}
.disparador:hover:not(:disabled), .disparador[aria-expanded="true"] {
  background: var(--fondo); border-color: var(--borde);
}
.avatar {
  display: grid; place-items: center; width: 2rem; height: 2rem; border-radius: 50%;
  background: var(--marca); color: var(--blanco); font-size: .78rem; font-weight: 700; letter-spacing: .03em;
}
/* El nombre solo cabe junto al menú en pantallas anchas; en las demás
   basta con las iniciales y el nombre completo está dentro del panel. */
.quien { display: none; text-align: left; line-height: 1.2; }
.quien strong { display: block; font-size: .88rem; }
.quien span { font-size: .75rem; color: var(--tinta-suave); }
@media (min-width: 1440px) { .quien { display: block; } }
.flecha { color: var(--tinta-suave); transition: transform var(--transicion); }
.disparador[aria-expanded="true"] .flecha { transform: rotate(180deg); }

.panel {
  position: absolute; right: 0; top: calc(100% + .5rem); z-index: 30;
  width: 16.5rem; padding: .35rem;
  background: var(--superficie); border: 1px solid var(--borde);
  border-radius: var(--radio); box-shadow: var(--sombra-alta);
  transform-origin: top right;
}
.cabecera {
  display: grid; gap: .1rem; margin: 0 0 .35rem; padding: .6rem .7rem .75rem;
  border-bottom: 1px solid var(--borde); line-height: 1.3; overflow-wrap: anywhere;
}
.cabecera strong { font-size: .95rem; }
.cabecera span { font-size: .8rem; color: var(--tinta-suave); }

.opcion {
  display: flex; align-items: center; gap: .6rem; width: 100%;
  padding: .55rem .7rem; border: 0; border-radius: 6px;
  background: none; color: var(--tinta); font-size: .92rem; font-weight: 500;
  text-align: left; text-decoration: none;
}
.opcion:hover:not(:disabled) { background: var(--fondo); }
.opcion:focus-visible { outline-offset: -2px; }
.salir { color: var(--alerta); }
.salir:hover:not(:disabled) { background: var(--alerta-tenue); }

.desplegar-enter-active, .desplegar-leave-active { transition: opacity var(--transicion), transform var(--transicion); }
.desplegar-enter-from, .desplegar-leave-to { opacity: 0; transform: translateY(-4px) scale(.98); }
</style>
