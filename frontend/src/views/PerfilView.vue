<script setup>
// P20 Mi perfil y seguridad (RF18 propuesto, CC-13), según el wireframe y la
// Tabla 33 de la Práctica N.° 7. Para todos los roles.
//
// Los datos de la cuenta son de solo lectura: el usuario no puede cambiar su
// propio rol ni sus sedes. El cambio de contraseña lo resuelve el servidor
// con el formulario de Django: comprueba la actual, aplica la política de
// contraseñas y cierra las demás sesiones abiertas de la cuenta.
//
// La verificación en dos pasos (P02) no está construida: se muestra su
// estado, sin nada que configurar.
//
// Con una contraseña temporal (alta o restablecimiento) el router trae aquí
// al usuario y no lo deja salir hasta cambiarla; el servidor bloquea el
// resto de la API por su cuenta.
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '../services/api'
import { useSesion } from '../stores/sesion'

const sesion = useSesion()
const router = useRouter()
const obligado = computed(() => Boolean(sesion.usuario?.debe_cambiar_contrasena))

const formulario = ref({ contrasena_actual: '', contrasena_nueva: '', confirmacion: '' })
const guardando = ref(false)
const error = ref(null)
const camposConError = ref({})
const aviso = ref(null)

const ultimoAcceso = computed(() => {
  const valor = sesion.usuario?.ultimo_acceso_en
  return valor
    ? new Date(valor).toLocaleString('es-PE', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' })
    : 'sin registro'
})
const sedes = computed(() => sesion.sedes.map((s) => s.nombre).join(', ') || '—')
const completo = computed(() => Object.values(formulario.value).every((v) => v.length > 0))

async function guardar () {
  guardando.value = true
  error.value = null
  aviso.value = null
  camposConError.value = {}
  try {
    await api.post('/sesion/contrasena/', formulario.value)
    formulario.value = { contrasena_actual: '', contrasena_nueva: '', confirmacion: '' }
    if (obligado.value) {
      sesion.usuario.debe_cambiar_contrasena = false
      router.push({ name: sesion.necesitaElegirSede ? 'elegir-sede' : 'panel' })
      return
    }
    aviso.value = 'Contraseña cambiada. Se cerraron las demás sesiones abiertas con su cuenta.'
  } catch (problema) {
    error.value = problema.mensaje
    camposConError.value = problema.codigo === 'contrasena-actual-incorrecta'
      ? { contrasena_actual: true }
      : (problema.campos ?? {})
  } finally {
    guardando.value = false
  }
}
</script>

<template>
  <main>
    <div class="encabezado">
      <h1>Mi perfil y seguridad</h1>
    </div>

    <p v-if="obligado" class="aviso-ajuste" role="alert">
      Está usando una contraseña temporal. Elija una contraseña propia para continuar; en
      «Contraseña actual» escriba la temporal que le entregaron.
    </p>

    <section class="tarjeta perfil-datos" aria-labelledby="titulo-cuenta">
      <h2 id="titulo-cuenta">
        {{ sesion.usuario?.nombre_completo }}
      </h2>
      <p>{{ sesion.usuario?.correo }} · {{ sesion.usuario?.rol_descripcion }} · Sedes: {{ sedes }}</p>
      <p>Último acceso: {{ ultimoAcceso }}</p>
    </section>

    <form class="tarjeta" aria-labelledby="titulo-contrasena" @submit.prevent="guardar">
      <h2 id="titulo-contrasena">
        Cambiar contraseña
      </h2>
      <div class="campo">
        <label for="c-actual">Contraseña actual *</label>
        <input
          id="c-actual"
          v-model="formulario.contrasena_actual"
          type="password"
          autocomplete="current-password"
          required
          :aria-invalid="'contrasena_actual' in camposConError"
        >
      </div>
      <div class="fila-campos">
        <div class="campo">
          <label for="c-nueva">Nueva contraseña *</label>
          <input
            id="c-nueva"
            v-model="formulario.contrasena_nueva"
            type="password"
            autocomplete="new-password"
            required
            aria-describedby="ayuda-contrasena"
            :aria-invalid="'contrasena_nueva' in camposConError"
          >
        </div>
        <div class="campo">
          <label for="c-confirmacion">Repetir la nueva *</label>
          <input
            id="c-confirmacion"
            v-model="formulario.confirmacion"
            type="password"
            autocomplete="new-password"
            required
            :aria-invalid="'contrasena_nueva' in camposConError"
          >
        </div>
      </div>
      <p id="ayuda-contrasena" class="ayuda">
        Al menos 10 caracteres; no puede parecerse a sus datos, ser una contraseña común ni tener solo números.
      </p>

      <p v-if="error" role="alert">
        {{ error }}
      </p>
      <p v-if="aviso" class="aviso-ok" role="status">
        {{ aviso }}
      </p>

      <div class="dialogo-acciones">
        <button type="submit" :disabled="!completo || guardando">
          {{ guardando ? 'Guardando…' : 'Guardar cambios' }}
        </button>
      </div>
    </form>

    <section class="tarjeta perfil-segundo-factor" aria-labelledby="titulo-dos-pasos">
      <h2 id="titulo-dos-pasos">
        Verificación en dos pasos
      </h2>
      <p>
        <span class="etiqueta" :class="sesion.usuario?.segundo_factor_activo ? 'ATENDIDA' : 'NO_ASISTIO'">
          {{ sesion.usuario?.segundo_factor_activo ? 'Activada' : 'Desactivada' }}
        </span>
        Todavía no se puede configurar desde el sistema (P02 pendiente).
      </p>
    </section>
  </main>
</template>
