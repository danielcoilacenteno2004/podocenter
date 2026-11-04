<script setup>
// P01 Acceso al sistema (CU02).
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useSesion } from '../stores/sesion'

const sesion = useSesion()
const router = useRouter()

const correo = ref('')
const contrasena = ref('')
const error = ref(null)
const enviando = ref(false)

async function ingresar () {
  enviando.value = true
  error.value = null
  try {
    await sesion.iniciarSesion(correo.value, contrasena.value)
    router.push({ name: sesion.necesitaElegirSede ? 'elegir-sede' : 'panel' })
  } catch (problema) {
    error.value = problema.mensaje
  } finally {
    enviando.value = false
  }
}
</script>

<template>
  <div class="acceso">
    <section class="tarjeta" aria-labelledby="titulo-acceso">
      <p class="marca">
        <svg width="26" height="26" viewBox="0 0 24 24" aria-hidden="true">
          <path d="M7 3.5c1.7 0 2.8 1.6 2.8 3.6S8.7 10.7 7 10.7 4.2 9.1 4.2 7.1 5.3 3.5 7 3.5Z" fill="#0f6f6a"/>
          <path d="M12.6 4.6c1.3 0 2.1 1.2 2.1 2.7s-.8 2.7-2.1 2.7-2.1-1.2-2.1-2.7.8-2.7 2.1-2.7ZM16.9 7c1 0 1.7 1 1.7 2.2s-.7 2.2-1.7 2.2-1.7-1-1.7-2.2.7-2.2 1.7-2.2Z" fill="#0f6f6a" opacity=".75"/>
          <path d="M6.5 12.4c2.7 0 4.6 1 6.9 2.3 2 1.1 3.2 2.2 3.2 3.8 0 1.6-1.4 2.6-3.3 2.6-1.6 0-2.5-.5-4.2-.5-1.5 0-2.4.4-3.6.4-1.7 0-3-1-3-2.9 0-2 1.3-3.4 2.1-4.6.5-.7 1-1.1 1.9-1.1Z" fill="#0f6f6a"/>
        </svg>
        PodoCenter
      </p>

      <h1 id="titulo-acceso">Ingresar</h1>
      <p style="color:var(--tinta-suave);margin:.25rem 0 1.25rem">
        Gestión del centro de podología
      </p>

      <p v-if="error" role="alert">{{ error }}</p>

      <form @submit.prevent="ingresar">
        <div class="campo">
          <label for="correo">Correo</label>
          <input id="correo" v-model="correo" type="email" autocomplete="username"
                 required autofocus>
        </div>
        <div class="campo">
          <label for="contrasena">Contraseña</label>
          <input id="contrasena" v-model="contrasena" type="password"
                 autocomplete="current-password" required>
        </div>
        <button type="submit" :disabled="enviando" style="width:100%">
          {{ enviando ? 'Verificando…' : 'Ingresar' }}
        </button>
      </form>

      <p class="credenciales">
        Entorno de demostración. Administradora del centro:
        <code>gerencia@piessanos.pe</code> · Podóloga:
        <code>podologa@piessanos.pe</code> · Contraseña:
        <code>Podocenter2026</code>
      </p>
    </section>
  </div>
</template>
