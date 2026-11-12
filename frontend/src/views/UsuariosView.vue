<script setup>
// P17 Usuarios y roles y P27 Crear o editar usuario (CU01), solo para la
// administradora del centro (Práctica N.° 7, Tablas 27 y 28).
//
// Las reglas son del servidor: correo duplicado, rol no permitido, usuario
// sin sede y «último administrador» al desactivar llegan con su código y se
// muestran tal cual.
//
// La edición cambia solo nombres, apellidos y correo. Rol y sedes no se
// editan aquí: el PATCH de la API cambia el rol sin pasar por la regla del
// último administrador e ignora las sedes. Activar y desactivar van por sus
// propias rutas (DELETE y reactivar), que sí pasan por el servicio.
// Del wireframe no se construyen «Usuario» (el acceso es por correo) ni
// «Atiende citas» (no está modelado).
//
// Mientras no exista el enlace por correo (P24), el alta y «Restablecer
// contraseña» devuelven una contraseña temporal que se muestra una sola vez;
// el servidor obliga a cambiarla al entrar.
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { api } from '../services/api'
import { useSesion } from '../stores/sesion'

const sesion = useSesion()

const ROLES = [['ADMIN_CENTRO', 'Administrador del centro'], ['PODOLOGA', 'Podóloga']]
const nombreDelRol = (rol) => (ROLES.find(([v]) => v === rol) ?? [])[1] ?? rol

const usuarios = ref([])
const sedesActivas = ref([])
const filtros = ref({ rol: '', esta_activo: '' })
const cargando = ref(false)
const error = ref(null)
const aviso = ref(null)
const porConfirmar = ref(null)   // id del usuario cuya baja espera confirmación
const porRestablecer = ref(null) // id del usuario cuyo restablecimiento espera confirmación
const credencial = ref(null)     // { correo, contrasena }: se muestra una sola vez

const dialogo = ref(null)
const primerCampo = ref(null)
const editando = ref(null)       // null = alta
const formulario = ref({})
const guardando = ref(false)
const errorFormulario = ref(null)
const camposConError = ref({})

const completo = computed(() => {
  const f = formulario.value
  const base = f.nombres?.trim() && f.apellidos?.trim() && f.correo?.trim()
  return Boolean(editando.value ? base : base && f.rol && f.sedes_ids?.length)
})

let turno = 0
async function cargar () {
  const mio = ++turno
  cargando.value = true
  error.value = null
  try {
    const params = {}
    if (filtros.value.rol) params.rol = filtros.value.rol
    if (filtros.value.esta_activo !== '') params.esta_activo = filtros.value.esta_activo
    const { data } = await api.get('/usuarios/', { params })
    if (mio === turno) usuarios.value = data.results ?? data
  } catch (problema) {
    if (mio === turno) error.value = problema.mensaje
  } finally {
    if (mio === turno) cargando.value = false
  }
}

async function abrir (usuario = null) {
  editando.value = usuario
  errorFormulario.value = null
  camposConError.value = {}
  formulario.value = usuario
    ? { nombres: usuario.nombres, apellidos: usuario.apellidos, correo: usuario.correo }
    : { nombres: '', apellidos: '', correo: '', rol: 'PODOLOGA', sedes_ids: [] }
  if (!usuario && !sedesActivas.value.length) {
    try {
      const { data } = await api.get('/sedes/', { params: { esta_activa: true } })
      sedesActivas.value = data.results ?? data
    } catch (problema) {
      error.value = problema.mensaje
      return
    }
  }
  dialogo.value.showModal()
  await nextTick()
  primerCampo.value?.focus()
}

async function guardar () {
  credencial.value = null
  guardando.value = true
  errorFormulario.value = null
  camposConError.value = {}
  try {
    if (editando.value) {
      const { nombres, apellidos, correo } = formulario.value
      await api.patch(`/usuarios/${editando.value.id}/`, { nombres, apellidos, correo })
      aviso.value = `Datos de ${nombres} ${apellidos} actualizados.`
    } else {
      const { data } = await api.post('/usuarios/', formulario.value)
      aviso.value = `Usuario ${data.nombre_completo} creado.`
      credencial.value = { correo: data.correo, contrasena: data.contrasena_temporal }
    }
    dialogo.value.close()
    await cargar()
  } catch (problema) {
    errorFormulario.value = problema.mensaje
    camposConError.value = problema.campos ?? {}
  } finally {
    guardando.value = false
  }
}

async function desactivar (usuario) {
  porConfirmar.value = null
  error.value = null
  try {
    await api.delete(`/usuarios/${usuario.id}/`)
    aviso.value = `${usuario.nombre_completo} quedó desactivado. Conserva sus citas y atenciones.`
    await cargar()
  } catch (problema) {
    error.value = problema.mensaje
  }
}

async function restablecer (usuario) {
  porRestablecer.value = null
  credencial.value = null
  error.value = null
  try {
    const { data } = await api.post(`/usuarios/${usuario.id}/restablecer-contrasena/`)
    aviso.value = `Contraseña de ${usuario.nombre_completo} restablecida. Sus sesiones abiertas se cerraron.`
    credencial.value = { correo: usuario.correo, contrasena: data.contrasena_temporal }
  } catch (problema) {
    error.value = problema.mensaje
  }
}

async function reactivar (usuario) {
  error.value = null
  try {
    await api.post(`/usuarios/${usuario.id}/reactivar/`)
    aviso.value = `${usuario.nombre_completo} vuelve a estar activo.`
    await cargar()
  } catch (problema) {
    error.value = problema.mensaje
  }
}

watch(filtros, cargar, { deep: true })
onMounted(cargar)
</script>

<template>
  <main>
    <div class="encabezado encabezado-con-accion">
      <div>
        <h1>Usuarios y roles</h1>
        <p>Personas que trabajan en el centro y en qué sedes.</p>
      </div>
      <button type="button" @click="abrir()">
        + Nuevo usuario
      </button>
    </div>

    <form class="filtros" aria-label="Filtros de usuarios" @submit.prevent>
      <div class="campo">
        <label for="filtro-rol">Rol</label>
        <select id="filtro-rol" v-model="filtros.rol">
          <option value="">
            Todos
          </option>
          <option v-for="[valor, etiqueta] in ROLES" :key="valor" :value="valor">
            {{ etiqueta }}
          </option>
        </select>
      </div>
      <div class="campo">
        <label for="filtro-estado">Estado</label>
        <select id="filtro-estado" v-model="filtros.esta_activo">
          <option value="">
            Todos
          </option>
          <option :value="true">
            Activos
          </option>
          <option :value="false">
            Desactivados
          </option>
        </select>
      </div>
    </form>

    <p v-if="error" role="alert">
      {{ error }}
    </p>
    <div v-if="aviso" class="aviso-ok" role="status">
      <p>{{ aviso }}</p>
      <div v-if="credencial" class="credencial-temporal">
        <p>
          Usuario: <strong>{{ credencial.correo }}</strong> ·
          Contraseña temporal: <code>{{ credencial.contrasena }}</code>
        </p>
        <p class="ayuda">
          Se muestra solo esta vez. Entréguela en persona o por un canal seguro; el sistema
          le pedirá cambiarla al entrar.
        </p>
      </div>
    </div>

    <section class="tarjeta">
      <p v-if="cargando" role="status">
        Cargando usuarios…
      </p>
      <p v-else-if="!usuarios.length" class="vacio">
        Ningún usuario coincide con los filtros.
      </p>
      <table v-else class="administracion">
        <caption>{{ usuarios.length }} usuario(s)</caption>
        <thead>
          <tr>
            <th scope="col">
              Usuario
            </th>
            <th scope="col">
              Rol
            </th>
            <th scope="col">
              Sedes
            </th>
            <th scope="col">
              Activo
            </th>
            <th scope="col">
              <span class="solo-lectores">Acciones</span>
            </th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="u in usuarios" :key="u.id">
            <td>
              <strong>{{ u.nombre_completo }}</strong>
              <span class="secundario-celda">{{ u.correo }}</span>
            </td>
            <td>{{ nombreDelRol(u.rol) }}</td>
            <td>{{ u.sedes.map((s) => s.nombre).join(', ') || '—' }}</td>
            <td>
              <span class="etiqueta" :class="u.esta_activo ? 'ATENDIDA' : 'NO_ASISTIO'">
                {{ u.esta_activo ? 'Sí' : 'No' }}
              </span>
            </td>
            <td class="accion">
              <div v-if="porConfirmar === u.id" class="acciones-fila confirmacion">
                <span>¿Desactivar?</span>
                <button class="boton-fila" type="button" @click="desactivar(u)">
                  Sí, desactivar
                </button>
                <button class="secundario boton-fila" type="button" @click="porConfirmar = null">
                  No
                </button>
              </div>
              <div v-else-if="porRestablecer === u.id" class="acciones-fila confirmacion">
                <span>¿Dar una contraseña nueva?</span>
                <button class="boton-fila" type="button" @click="restablecer(u)">
                  Sí, restablecer
                </button>
                <button class="secundario boton-fila" type="button" @click="porRestablecer = null">
                  No
                </button>
              </div>
              <div v-else class="acciones-fila">
                <button class="secundario boton-fila" type="button" :aria-label="`Editar a ${u.nombre_completo}`" @click="abrir(u)">
                  Editar
                </button>
                <button
                  v-if="u.esta_activo && u.id !== sesion.usuario?.id"
                  class="secundario boton-fila"
                  type="button"
                  :aria-label="`Restablecer la contraseña de ${u.nombre_completo}`"
                  @click="porRestablecer = u.id"
                >
                  Restablecer contraseña
                </button>
                <button
                  v-if="u.esta_activo"
                  class="secundario boton-fila"
                  type="button"
                  :aria-label="`Desactivar a ${u.nombre_completo}`"
                  @click="porConfirmar = u.id"
                >
                  Desactivar
                </button>
                <button
                  v-else
                  class="secundario boton-fila"
                  type="button"
                  :aria-label="`Reactivar a ${u.nombre_completo}`"
                  @click="reactivar(u)"
                >
                  Reactivar
                </button>
              </div>
            </td>
          </tr>
        </tbody>
      </table>
    </section>

    <dialog ref="dialogo" class="dialogo" aria-labelledby="titulo-usuario">
      <form method="dialog" class="dialogo-cabecera">
        <h2 id="titulo-usuario">
          {{ editando ? `Editar a ${editando.nombre_completo}` : 'Nuevo usuario' }}
        </h2>
        <button class="enlace" type="submit" aria-label="Cerrar">
          ×
        </button>
      </form>
      <form class="dialogo-cuerpo" @submit.prevent="guardar">
        <div class="fila-campos">
          <div class="campo">
            <label for="u-nombres">Nombres *</label>
            <input id="u-nombres" ref="primerCampo" v-model="formulario.nombres" maxlength="80" required :aria-invalid="'nombres' in camposConError">
          </div>
          <div class="campo">
            <label for="u-apellidos">Apellidos *</label>
            <input id="u-apellidos" v-model="formulario.apellidos" maxlength="80" required :aria-invalid="'apellidos' in camposConError">
          </div>
        </div>
        <div class="campo">
          <label for="u-correo">Correo *</label>
          <input id="u-correo" v-model="formulario.correo" type="email" required :aria-invalid="'correo' in camposConError" aria-describedby="ayuda-correo">
          <p id="ayuda-correo" class="ayuda">
            Es el nombre de acceso al sistema.
          </p>
        </div>

        <template v-if="!editando">
          <div class="campo">
            <label for="u-rol">Rol *</label>
            <select id="u-rol" v-model="formulario.rol" required :aria-invalid="'rol' in camposConError">
              <option v-for="[valor, etiqueta] in ROLES" :key="valor" :value="valor">
                {{ etiqueta }}
              </option>
            </select>
          </div>
          <fieldset class="campo opciones">
            <legend>Sedes asignadas *</legend>
            <label v-for="s in sedesActivas" :key="s.id">
              <input v-model="formulario.sedes_ids" type="checkbox" :value="s.id">
              {{ s.nombre }}
            </label>
          </fieldset>
        </template>
        <div v-else class="resumen-cita">
          <p><strong>{{ nombreDelRol(editando.rol) }}</strong> · {{ editando.sedes.map((s) => s.nombre).join(', ') || 'sin sedes' }}</p>
          <p>El rol y las sedes no se pueden cambiar desde aquí todavía.</p>
        </div>

        <p v-if="errorFormulario" role="alert">
          {{ errorFormulario }}
        </p>
        <div class="dialogo-acciones">
          <button class="secundario" type="button" @click="dialogo.close()">
            Cancelar
          </button>
          <button type="submit" :disabled="!completo || guardando">
            {{ guardando ? 'Guardando…' : (editando ? 'Guardar cambios' : 'Crear usuario') }}
          </button>
        </div>
      </form>
    </dialog>
  </main>
</template>
