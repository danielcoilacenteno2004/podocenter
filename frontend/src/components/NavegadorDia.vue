<script setup>
// Navegación por días: anterior, selector de fecha, siguiente y «Hoy».
// Funciona con v-model (defineModel): el componente no guarda la fecha, la
// propone, y la pantalla decide qué hacer con ella (la del panel, por
// ejemplo, la lleva a la dirección). `tono` lo adapta a un fondo claro u
// oscuro de la paleta.
import { computed, useId } from 'vue'
import { hoy, moverDias } from '../formato'
import IconoTrazo from './IconoTrazo.vue'

const fecha = defineModel({ type: String, required: true })

defineProps({
  tono: { type: String, default: 'claro', validator: (valor) => ['claro', 'oscuro'].includes(valor) },
  etiqueta: { type: String, default: 'Día' }
})

const idCampo = useId()
const esHoy = computed(() => fecha.value === hoy())
</script>

<template>
  <div class="navegador-dia" :class="`sobre-${tono}`" role="group" :aria-label="etiqueta">
    <button type="button" class="paso" aria-label="Día anterior" @click="fecha = moverDias(fecha, -1)">
      <IconoTrazo nombre="anterior" />
    </button>
    <label :for="idCampo" class="solo-lectores">{{ etiqueta }}</label>
    <input :id="idCampo" v-model="fecha" type="date" required>
    <button type="button" class="paso" aria-label="Día siguiente" @click="fecha = moverDias(fecha, 1)">
      <IconoTrazo nombre="siguiente" />
    </button>
    <button type="button" class="hoy" :disabled="esHoy" @click="fecha = hoy()">
      Hoy
    </button>
  </div>
</template>

<style scoped>
.navegador-dia { display: flex; align-items: center; gap: .35rem; }
.navegador-dia input { width: auto; min-width: 0; padding-block: .45rem; }
.paso, .hoy {
  display: grid; place-items: center; height: 2.35rem; padding: 0 .55rem;
  background: transparent; color: var(--marca); border-color: var(--borde);
}
.hoy { padding-inline: .9rem; font-size: .9rem; }
.paso:hover:not(:disabled), .hoy:hover:not(:disabled) { background: var(--marca-tenue); border-color: var(--oficial-claro); }

/* Sobre la franja oscura: líneas y fondos de blanco translúcido. */
.sobre-oscuro { --linea: color-mix(in srgb, var(--blanco) 28%, transparent); }
.sobre-oscuro .paso, .sobre-oscuro .hoy { color: var(--blanco); border-color: var(--linea); }
.sobre-oscuro .paso:hover:not(:disabled), .sobre-oscuro .hoy:hover:not(:disabled) {
  background: color-mix(in srgb, var(--blanco) 12%, transparent); border-color: var(--blanco);
}
.sobre-oscuro input {
  color: var(--blanco); color-scheme: dark;
  background: color-mix(in srgb, var(--blanco) 10%, transparent); border-color: var(--linea);
}
.sobre-oscuro input:hover:not(:disabled) { border-color: var(--blanco); }
.sobre-oscuro input:focus-visible { border-color: var(--blanco); box-shadow: 0 0 0 3px color-mix(in srgb, var(--blanco) 25%, transparent); }
.sobre-oscuro button:focus-visible { outline-color: var(--blanco); }
</style>
