<script setup>
// P01 Acceso al sistema (CU02).
import { nextTick, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useSesion } from '../stores/sesion'
import MarcaArtemisa from '../components/MarcaArtemisa.vue'
import IconoTrazo from '../components/IconoTrazo.vue'

// Cuentas del entorno de demostración (las de `cargar_demo`). Pulsarlas
// rellena el formulario; no ingresan solas, para que se vea el recorrido real.
const CUENTAS_DEMO = [
  { correo: 'gerencia@piessanos.pe', rol: 'Administradora del centro' },
  { correo: 'podologa@piessanos.pe', rol: 'Podóloga' }
]
const CONTRASENA_DEMO = 'Podocenter2026'

const sesion = useSesion()
const router = useRouter()

const correo = ref('')
const contrasena = ref('')
const error = ref(null)
const enviando = ref(false)
const mostrarContrasena = ref(false)
const mayusculasActivas = ref(false)
const campoContrasena = ref(null)

// El error se refiere a lo que se envió: en cuanto se corrige un dato, sobra.
watch([correo, contrasena], () => { error.value = null })

// Un Bloq Mayús olvidado es la causa más común de una contraseña «incorrecta».
function revisarMayusculas (evento) {
  mayusculasActivas.value = evento.getModifierState?.('CapsLock') ?? false
}

function usarCuenta (cuenta) {
  correo.value = cuenta.correo
  contrasena.value = CONTRASENA_DEMO
}

async function ingresar () {
  enviando.value = true
  error.value = null
  try {
    await sesion.iniciarSesion(correo.value, contrasena.value)
    router.push({ name: sesion.necesitaElegirSede ? 'elegir-sede' : 'panel' })
  } catch (problema) {
    error.value = problema.mensaje
    // Se deja el foco en la contraseña, que es lo que casi siempre se corrige.
    await nextTick()
    campoContrasena.value?.select()
  } finally {
    enviando.value = false
  }
}
</script>

<template>
  <div class="ingreso">
    <aside class="ingreso-marca">
      <MarcaArtemisa fondo="oscuro" />
      <div>
        <p class="ingreso-lema">Gestión del centro de podología</p>
      </div>
    </aside>

    <main class="ingreso-panel">
      <section class="ingreso-formulario" aria-labelledby="titulo-acceso">
        <h1 id="titulo-acceso">Ingresar</h1>
        <p class="subtitulo">Escriba su correo y su contraseña.</p>

        <Transition name="aparecer">
          <p v-if="error" role="alert">{{ error }}</p>
        </Transition>

        <form @submit.prevent="ingresar">
          <div class="campo">
            <label for="correo">Correo</label>
            <input id="correo" v-model.trim="correo" type="email" autocomplete="username"
                   placeholder="nombre@centro.pe" required autofocus>
          </div>
          <div class="campo">
            <label for="contrasena">Contraseña</label>
            <div class="campo-con-boton">
              <input id="contrasena" ref="campoContrasena" v-model="contrasena"
                     :type="mostrarContrasena ? 'text' : 'password'"
                     autocomplete="current-password" required
                     aria-describedby="aviso-mayusculas"
                     @keydown="revisarMayusculas" @keyup="revisarMayusculas"
                     @blur="mayusculasActivas = false">
              <button type="button" :aria-pressed="mostrarContrasena"
                      :aria-label="mostrarContrasena ? 'Ocultar la contraseña' : 'Mostrar la contraseña'"
                      @click="mostrarContrasena = !mostrarContrasena">
                <IconoTrazo :nombre="mostrarContrasena ? 'ojo-tachado' : 'ojo'" />
              </button>
            </div>
            <p id="aviso-mayusculas" class="ayuda aviso-mayusculas" role="status">
              <template v-if="mayusculasActivas">Bloq Mayús está activado.</template>
            </p>
          </div>
          <button class="bloque-completo" type="submit" :disabled="enviando" :aria-busy="enviando">
            <span v-if="enviando" class="rueda-carga" aria-hidden="true" />
            {{ enviando ? 'Verificando…' : 'Ingresar' }}
          </button>
        </form>

        <section class="credenciales" aria-labelledby="titulo-demo">
          <h2 id="titulo-demo">Entorno de demostración</h2>
          <ul>
            <li v-for="cuenta in CUENTAS_DEMO" :key="cuenta.correo">
              <button type="button" @click="usarCuenta(cuenta)">
                {{ cuenta.correo }}
                <span>{{ cuenta.rol }}</span>
              </button>
            </li>
          </ul>
          <p>Contraseña de ambas: <code>{{ CONTRASENA_DEMO }}</code></p>
        </section>
      </section>
    </main>
  </div>
</template>
