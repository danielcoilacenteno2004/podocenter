<script setup>
// Logo y nombre de la marca, sin cuadro de fondo, como firma una marca real.
// El logo se pinta con una máscara sobre el PNG y toma el color del texto
// (currentColor), así una sola regla colorea el logo y el nombre:
//  - «claro» (barra, sobre blanco): logo y nombre en #3C5154;
//  - «oscuro» (login, sobre #3C5154): logo y nombre en blanco.
// La combinación #57696D sobre #A1B5AC de la paleta queda para cuando el
// fondo sea #A1B5AC. El tamaño sigue al tamaño de letra del contexto (em).
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
    <span class="logo" aria-hidden="true" />
    Artemisa
  </span>
</template>

<style scoped>
.marca { display: flex; align-items: center; gap: .45em; font-weight: 700; letter-spacing: -.02em; }
.logo {
  width: 1.6em; height: 1.6em; flex: none;
  background: currentColor;
  mask: url("/logo-artemisa.png") center / contain no-repeat;
}
.sobre-claro { color: var(--marca); }
.sobre-oscuro { color: var(--blanco); }
</style>
