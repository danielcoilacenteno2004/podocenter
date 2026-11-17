<script setup>
// Tarjeta estándar de la interfaz. Toda superficie con contenido propio pasa
// por aquí, para que el espaciado, la cabecera y el pie sean iguales en todas
// las pantallas.
//  - La cabecera aparece solo si hay `titulo` o acciones: en los listados el
//    título ya lo da el h1 de la página y repetirlo sería ruido.
//  - `etiqueta` elige el elemento raíz: `section` o `form` (los atributos y
//    eventos que se le pasan, como @submit, llegan a ese elemento).
//  - Slots: el contenido, `acciones` (a la derecha del título) y `pie`.
import { useId } from 'vue'
import IconoTrazo from './IconoTrazo.vue'

defineProps({
  titulo: { type: String, default: '' },
  descripcion: { type: String, default: '' },
  icono: { type: String, default: '' },
  etiqueta: { type: String, default: 'section', validator: (valor) => ['section', 'form', 'div'].includes(valor) }
})

// Identificador único por instancia: enlaza el título con la región sin
// que cada pantalla tenga que inventar uno.
const idTitulo = useId()
</script>

<template>
  <component :is="etiqueta" class="tarjeta" :aria-labelledby="titulo ? idTitulo : undefined">
    <header v-if="titulo || $slots.acciones" class="tarjeta-cabecera">
      <span v-if="icono" class="tarjeta-icono"><IconoTrazo :nombre="icono" /></span>
      <div v-if="titulo" class="tarjeta-titulos">
        <h2 :id="idTitulo">{{ titulo }}</h2>
        <p v-if="descripcion">{{ descripcion }}</p>
      </div>
      <div v-if="$slots.acciones" class="tarjeta-acciones">
        <slot name="acciones" />
      </div>
    </header>

    <div class="tarjeta-cuerpo">
      <slot />
    </div>

    <footer v-if="$slots.pie" class="tarjeta-pie">
      <slot name="pie" />
    </footer>
  </component>
</template>

<style scoped>
/* Columna flexible: si la cuadrícula estira la tarjeta, el cuerpo absorbe el
   alto sobrante y el pie queda abajo, alineado con el de su vecina. */
.tarjeta { display: flex; flex-direction: column; }

.tarjeta-cabecera { display: flex; align-items: center; gap: .75rem; margin-bottom: 1.1rem; }
.tarjeta-icono {
  display: grid; place-items: center; width: 2.25rem; height: 2.25rem; flex: none;
  border-radius: 10px; background: var(--marca-tenue); color: var(--marca);
}
.tarjeta-titulos { min-width: 0; }
.tarjeta-titulos h2 { margin: 0; font-size: 1.02rem; line-height: 1.3; }
.tarjeta-titulos p { margin: .1rem 0 0; font-size: .85rem; color: var(--tinta-suave); }
.tarjeta-acciones { margin-left: auto; display: flex; align-items: center; gap: .5rem; flex-wrap: wrap; }

.tarjeta-cuerpo { flex: 1; min-width: 0; }

.tarjeta-pie {
  margin-top: 1.1rem; padding-top: .9rem; border-top: 1px solid var(--borde);
  font-size: .85rem; color: var(--tinta-suave);
}
/* El contenido del pie viene de la pantalla: :slotted() es la forma de
   alcanzarlo desde los estilos con alcance del componente. */
.tarjeta-pie > :slotted(p) { margin: 0; }
.tarjeta-pie > :slotted(:not(:first-child)) { margin-top: .6rem; }
</style>
