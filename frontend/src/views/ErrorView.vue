<script setup>
// P21 Sin permiso o error (RNF02), según el wireframe y la Tabla 34 de la
// Práctica N.° 7: una sola plantilla cuyo icono, título, mensaje y acción
// cambian con el código. El mensaje va en lenguaje del negocio, sin trazas
// ni nombres técnicos, y el código con la fecha queda siempre visible para
// que el usuario pueda citarlo al pedir ayuda.
//
// Cubre 403 (la sección no corresponde a su rol) y 404 (la dirección no
// existe). La ruta del 404 es pública para no rebotar al ingreso antes de
// mostrar el mensaje.
import { computed } from 'vue'
import { useSesion } from '../stores/sesion'
import TarjetaSeccion from '../components/TarjetaSeccion.vue'

const props = defineProps({ codigo: { type: Number, default: 404 } })
const sesion = useSesion()

const momento = new Date().toLocaleString('es-PE', {
  day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit'
})

const CASOS = {
  403: {
    icono: '⚠',
    titulo: 'No tiene acceso a esta sección',
    mensaje: () => `Su rol (${sesion.usuario?.rol_descripcion ?? 'sin rol'}) no incluye esta sección.`,
    ayuda: 'Si cree que es un error, consulte con el administrador de su centro.'
  },
  404: {
    icono: '?',
    titulo: 'Página no encontrada',
    mensaje: () => 'La dirección que abrió no corresponde a ninguna pantalla del sistema.',
    ayuda: 'Revise el enlace o vuelva al inicio.'
  }
}
const caso = computed(() => CASOS[props.codigo] ?? CASOS[404])
// Sin sesión, la salida útil es ingresar; con sesión, volver al inicio.
const salida = computed(() => sesion.autenticado
  ? { texto: 'Volver al inicio', destino: { name: 'panel' } }
  : { texto: 'Iniciar sesión', destino: { name: 'login' } })
</script>

<template>
  <div class="acceso">
    <TarjetaSeccion class="error-tarjeta" aria-labelledby="titulo-error">
      <p class="error-icono" aria-hidden="true">
        {{ caso.icono }}
      </p>
      <h1 id="titulo-error">
        {{ caso.titulo }}
      </h1>
      <p>{{ caso.mensaje() }}</p>
      <p class="error-ayuda">
        {{ caso.ayuda }}
      </p>
      <router-link class="boton boton-grande" :to="salida.destino">
        {{ salida.texto }}
      </router-link>
      <p class="error-codigo">
        Código de error: {{ codigo }} · {{ momento }}
      </p>
    </TarjetaSeccion>
  </div>
</template>
