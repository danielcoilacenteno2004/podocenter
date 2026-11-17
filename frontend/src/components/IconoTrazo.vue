<script>
// Iconos de trazo de la interfaz, todos con la misma rejilla (24 × 24), el
// mismo grosor y el color del texto que los rodea. Son decorativos: el
// significado lo lleva siempre el texto o la aria-label del control.
const TRAZOS = {
  abajo: 'm6 9 6 6 6-6',
  anterior: 'm15 18-6-6 6-6',
  siguiente: 'm9 18 6-6-6-6',
  flecha: 'M5 12h14M13 6l6 6-6 6',
  selector: 'm7 15 5 5 5-5M7 9l5-5 5 5',
  calendario: 'M8 2v4M16 2v4M3 10h18M5 4h14a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2Z',
  billete: 'M4 6h16a1 1 0 0 1 1 1v10a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1ZM12 14.5a2.5 2.5 0 1 0 0-5 2.5 2.5 0 0 0 0 5ZM6.5 12h.01M17.5 12h.01',
  reloj: 'M12 22a10 10 0 1 0 0-20 10 10 0 0 0 0 20ZM12 6v6l4 2',
  hecho: 'M12 22a10 10 0 1 0 0-20 10 10 0 0 0 0 20ZM8 12.5l2.5 2.5L16 9.5',
  cerrado: 'M12 22a10 10 0 1 0 0-20 10 10 0 0 0 0 20ZM4.9 4.9l14.2 14.2',
  historial: 'M3 12a9 9 0 1 0 3-6.7L3 8M3 3v5h5M12 7v5l3 2',
  candado: 'M7 11V7a5 5 0 0 1 10 0v4M5 11h14a1 1 0 0 1 1 1v8a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1v-8a1 1 0 0 1 1-1Z',
  escudo: 'M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10Z',
  info:'M12 22a10 10 0 1 0 0-20 10 10 0 0 0 0 20ZM12 16v-4M12 8h.01',
  sede: 'M12 21s-7-6.2-7-11.5a7 7 0 0 1 14 0C19 14.8 12 21 12 21ZM12 12a2.5 2.5 0 1 0 0-5 2.5 2.5 0 0 0 0 5Z',
  usuario: 'M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8ZM4 21a8 8 0 0 1 16 0',
  salir: 'M15 4h3a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2h-3M10 17l5-5-5-5M15 12H3',
  ojo: 'M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7S2 12 2 12ZM12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6Z',
  'ojo-tachado': 'M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7S2 12 2 12ZM12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6ZM4 4l16 16'
}
</script>

<script setup>
defineProps({
  nombre: { type: String, required: true, validator: (valor) => valor in TRAZOS },
  tamano: { type: [Number, String], default: 18 }
})
</script>

<template>
  <svg
    :width="tamano" :height="tamano" viewBox="0 0 24 24" fill="none" stroke="currentColor"
    stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false"
  >
    <path :d="TRAZOS[nombre]" />
  </svg>
</template>
