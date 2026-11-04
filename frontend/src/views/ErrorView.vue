<script setup>
// Página para una ruta que no existe. Se declara como pública para que no
// rebote al formulario de ingreso antes de poder mostrar el mensaje.
</script>

<template>
  <div class="acceso">
    <section class="tarjeta" style="text-align:center" aria-labelledby="titulo-error">
      <h1 id="titulo-error">Página no encontrada</h1>
      <p style="color:var(--tinta-suave)">
        La dirección que abrió no corresponde a ninguna pantalla del sistema.
      </p>
      <p style="margin-top:1.25rem">
        <router-link to="/">Volver al inicio</router-link>
      </p>
    </section>
  </div>
</template>
