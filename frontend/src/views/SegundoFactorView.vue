<script setup>
// P02 (alta) — Verificación en dos pasos (RF18).
//
// Tres momentos: escanear el QR, escribir el primer código para probar que
// la aplicación quedó bien configurada y guardar los diez códigos de
// recuperación, que se muestran solo esta vez. Para la administradora del
// centro y el administrador de plataforma es obligatoria: el router los trae
// aquí y el servidor rechaza el resto de la API hasta terminar.
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '../services/api'
import { useSesion } from '../stores/sesion'
import TarjetaSeccion from '../components/TarjetaSeccion.vue'

const sesion = useSesion()
const router = useRouter()
const obligatoria = computed(() => Boolean(sesion.usuario?.debe_activar_segundo_factor))

const alta = ref(null)
const codigo = ref('')
const codigosRecuperacion = ref([])
const guardados = ref(false)
const cargando = ref(false)
const error = ref(null)

async function generar () {
  cargando.value = true
  error.value = null
  try {
    const { data } = await api.post('/sesion/segundo-factor/alta/')
    alta.value = data
  } catch (problema) {
    error.value = problema.mensaje
  } finally {
    cargando.value = false
  }
}

async function confirmar () {
  cargando.value = true
  error.value = null
  try {
    const { data } = await api.post('/sesion/segundo-factor/confirmar/', { codigo: codigo.value })
    codigosRecuperacion.value = data.codigos_recuperacion
    sesion.actualizarUsuario(data.usuario)
    // El secreto ya no hace falta en la pantalla: no se deja en memoria.
    alta.value = null
  } catch (problema) {
    error.value = problema.mensaje
  } finally {
    cargando.value = false
  }
}

function copiarCodigos () {
  navigator.clipboard?.writeText(codigosRecuperacion.value.join('\n')).catch(() => {})
}

async function terminar () {
  if (sesion.usuario?.rol !== 'ADMIN_PLATAFORMA' && sesion.sedes.length === 0) {
    await sesion.cargarSedes()
  }
  router.push({ name: sesion.necesitaElegirSede ? 'elegir-sede' : 'panel' })
}

onMounted(() => {
  if (!sesion.usuario?.segundo_factor_activo) generar()
})
</script>

<template>
  <main>
    <div class="encabezado">
      <h1>Verificación en dos pasos</h1>
    </div>

    <p v-if="obligatoria" class="aviso-ajuste" role="alert">
      Su rol exige la verificación en dos pasos. Actívela para continuar: además de la contraseña,
      al ingresar se le pedirá un código de su teléfono.
    </p>

    <TarjetaSeccion v-if="codigosRecuperacion.length" icono="escudo" titulo="Guarde sus códigos de recuperación">
      <p>
        La verificación quedó activada. Si pierde el teléfono, cada uno de estos códigos le permite
        entrar una sola vez. <strong>No se volverán a mostrar.</strong> Anótelos o imprímalos y
        guárdelos fuera del teléfono.
      </p>
      <ol class="codigos-recuperacion">
        <li v-for="c in codigosRecuperacion" :key="c"><code>{{ c }}</code></li>
      </ol>
      <label class="casilla">
        <input v-model="guardados" type="checkbox">
        Ya guardé los códigos en un lugar seguro
      </label>
      <div class="dialogo-acciones">
        <button type="button" class="secundario" @click="copiarCodigos">Copiar</button>
        <button type="button" :disabled="!guardados" @click="terminar">Continuar</button>
      </div>
    </TarjetaSeccion>

    <TarjetaSeccion v-else-if="sesion.usuario?.segundo_factor_activo" icono="escudo" titulo="Ya está activada">
      <p class="ayuda">Al ingresar se le pide el código de su aplicación autenticadora.</p>
    </TarjetaSeccion>

    <TarjetaSeccion v-else etiqueta="form" icono="escudo" titulo="Activar con su aplicación autenticadora"
                    @submit.prevent="confirmar">
      <ol class="pasos-alta">
        <li>
          Instale en su teléfono una aplicación autenticadora (por ejemplo, Google Authenticator,
          Microsoft Authenticator o FreeOTP).
        </li>
        <li>
          Escanee este código QR con la aplicación.
          <div v-if="alta" class="qr-alta">
            <img :src="alta.qr" alt="Código QR para la aplicación autenticadora" width="220" height="220">
            <p class="ayuda">
              ¿No puede escanearlo? Escriba esta clave en la aplicación:
              <code class="clave-manual">{{ alta.secreto }}</code>
            </p>
          </div>
          <p v-else-if="cargando" class="ayuda">Generando el código…</p>
        </li>
        <li>
          <div class="campo">
            <label for="codigo-alta">Escriba el código de seis dígitos que muestra la aplicación</label>
            <input id="codigo-alta" v-model.trim="codigo" inputmode="numeric" autocomplete="one-time-code"
                   pattern="[0-9]{6}" maxlength="6" placeholder="000000" required>
          </div>
        </li>
      </ol>

      <p v-if="error" role="alert">{{ error }}</p>

      <div class="dialogo-acciones">
        <button type="button" class="secundario" :disabled="cargando" @click="generar">Generar otro QR</button>
        <button type="submit" :disabled="cargando || codigo.length !== 6 || !alta">
          {{ cargando ? 'Verificando…' : 'Activar' }}
        </button>
      </div>
    </TarjetaSeccion>
  </main>
</template>

<style scoped>
.pasos-alta { padding-left: 1.2rem; display: grid; gap: 1rem; }
.qr-alta { margin-top: .6rem; }
.qr-alta img { display: block; background: #fff; border-radius: 8px; max-width: 100%; height: auto; }
.clave-manual { word-break: break-all; letter-spacing: .08em; }
.codigos-recuperacion {
  display: grid; grid-template-columns: repeat(auto-fill, minmax(9rem, 1fr));
  gap: .4rem 1.2rem; padding-left: 1.4rem; font-size: 1.05rem;
}
</style>
