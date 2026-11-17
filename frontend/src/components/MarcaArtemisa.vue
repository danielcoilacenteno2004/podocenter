<script setup>
// Logo y nombre de la marca. El logo se pinta con una máscara sobre el PNG
// para que tome el color de la paleta oficial según el fondo donde va:
//  - «oscuro»: logo blanco, directamente sobre el #3C5154 del contenedor;
//  - «claro»: insignia #A1B5AC con el logo en #57696D.
// El tamaño sigue al tamaño de letra del contexto (todo en em).
defineProps({
  fondo: {
    type: String,
    default: 'claro',
    validator: (valor) => ['claro', 'oscuro'].includes(valor)
  }
})
</script>

<template>
  <span class="marca" :class="`sobre-${fondo}`">
    <span class="insignia" aria-hidden="true"><span class="logo" /></span>
    Artemisa
  </span>
</template>

<style scoped>
.marca { display: flex; align-items: center; gap: .6em; font-weight: 700; letter-spacing: -.02em; }
.insignia { display: grid; place-items: center; width: 2em; height: 2em; flex: none; border-radius: .55em; }
.logo {
  width: 78%; height: 78%;
  background: currentColor;
  mask: url("/logo-artemisa.png") center / contain no-repeat;
}
.sobre-claro .insignia { background: var(--oficial-claro); color: var(--oficial-medio); }
.sobre-oscuro .insignia { color: var(--blanco); }
.sobre-oscuro .logo { width: 100%; height: 100%; }
</style>
