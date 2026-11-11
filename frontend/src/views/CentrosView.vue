<script setup>
// P19 Centros clientes y P29 Crear o editar centro cliente (RF17), solo para
// el administrador de plataforma (Práctica N.° 7, Tablas 31 y 32). Ninguna de
// las dos da acceso a datos de pacientes.
//
// El alta crea el centro y su administrador inicial en una sola operación.
// Como P24 (definir la contraseña por enlace) no existe, el servidor genera
// una contraseña temporal que se muestra aquí una única vez.
//
// Suspender pide motivo y bloquea el ingreso de todos los usuarios del
// centro; reactivar lo devuelve. Un centro no se borra.
import { computed, nextTick, onMounted, ref } from 'vue'
import { api } from '../services/api'

const ESTADOS = { ACTIVO: ['Activo', 'ATENDIDA'], SUSPENDIDO: ['Suspendido', 'CANCELADA'], DEMO: ['Demostración', 'PROGRAMADA'] }

const centros = ref([])
const cargando = ref(false)
const error = ref(null)
const aviso = ref(null)
const credencial = ref(null)          // { correo, contrasena } tras un alta; se muestra una vez

const suspendiendo = ref(null)        // id del centro cuya suspensión se está confirmando
const motivo = ref('')
const campoMotivo = ref(null)

const dialogo = ref(null)
const primerCampo = ref(null)
const editando = ref(null)
// Forma completa desde el inicio: la ventana existe (oculta) antes de abrirse
// y lee formulario.administrador al renderizarse.
const vacio = () => ({
  ruc: '', nombre_comercial: '', razon_social: '', subdominio: '', correo_contacto: '',
  administrador: { nombres: '', apellidos: '', correo: '' }
})
const formulario = ref(vacio())
const guardando = ref(false)
const errorFormulario = ref(null)
const camposConError = ref({})

const completo = computed(() => {
  const f = formulario.value
  const centro = ['ruc', 'nombre_comercial', 'razon_social', 'subdominio', 'correo_contacto']
    .every((c) => (f[c] ?? '').trim())
  if (editando.value) return centro
  const a = f.administrador ?? {}
  return centro && ['nombres', 'apellidos', 'correo'].every((c) => (a[c] ?? '').trim())
})

const fecha = (valor) => new Date(valor).toLocaleDateString('es-PE', { day: '2-digit', month: '2-digit', year: 'numeric' })

async function cargar () {
  cargando.value = true
  error.value = null
  try {
    const { data } = await api.get('/centros/')
    centros.value = data.results ?? data
  } catch (problema) {
    error.value = problema.mensaje
  } finally {
    cargando.value = false
  }
}

async function abrir (centro = null) {
  editando.value = centro
  errorFormulario.value = null
  camposConError.value = {}
  formulario.value = centro
    ? {
        ruc: centro.ruc, nombre_comercial: centro.nombre_comercial, razon_social: centro.razon_social,
        subdominio: centro.subdominio, correo_contacto: centro.correo_contacto
      }
    : vacio()
  dialogo.value.showModal()
  await nextTick()
  primerCampo.value?.focus()
}

async function guardar () {
  guardando.value = true
  errorFormulario.value = null
  camposConError.value = {}
  try {
    if (editando.value) {
      await api.patch(`/centros/${editando.value.id}/`, formulario.value)
      aviso.value = `${formulario.value.nombre_comercial} actualizado.`
      credencial.value = null
    } else {
      const { data } = await api.post('/centros/', formulario.value)
      aviso.value = `${data.nombre_comercial} creado con su administrador inicial.`
      credencial.value = { correo: data.administrador.correo, contrasena: data.contrasena_temporal }
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

async function pedirSuspension (centro) {
  suspendiendo.value = centro.id
  motivo.value = ''
  await nextTick()
  campoMotivo.value?.[0]?.focus?.() ?? campoMotivo.value?.focus?.()
}

async function cambiarEstado (centro, estado) {
  error.value = null
  try {
    await api.patch(`/centros/${centro.id}/`, estado === 'SUSPENDIDO'
      ? { estado, motivo_suspension: motivo.value.trim() }
      : { estado })
    aviso.value = estado === 'SUSPENDIDO'
      ? `${centro.nombre_comercial || centro.razon_social} quedó suspendido: sus usuarios ya no pueden ingresar.`
      : `${centro.nombre_comercial || centro.razon_social} vuelve a estar activo.`
    credencial.value = null
    suspendiendo.value = null
    await cargar()
  } catch (problema) {
    error.value = problema.mensaje
  }
}

onMounted(cargar)
</script>

<template>
  <main>
    <div class="encabezado encabezado-con-accion">
      <div>
        <h1>Centros clientes</h1>
        <p>Centros que arriendan el sistema. Desde aquí no se ve ningún dato de pacientes.</p>
      </div>
      <button type="button" @click="abrir()">
        + Nuevo centro
      </button>
    </div>

    <p v-if="error" role="alert">
      {{ error }}
    </p>
    <div v-if="aviso" class="aviso-ok" role="status">
      <p>{{ aviso }}</p>
      <div v-if="credencial" class="credencial-temporal">
        <p>
          Administrador: <strong>{{ credencial.correo }}</strong> ·
          Contraseña temporal: <code>{{ credencial.contrasena }}</code>
        </p>
        <p class="ayuda">
          Se muestra solo esta vez. Comuníquela por un canal seguro; el administrador debe
          cambiarla en «Mi perfil» al entrar.
        </p>
      </div>
    </div>

    <section class="tarjeta">
      <p v-if="cargando" role="status">
        Cargando centros…
      </p>
      <p v-else-if="!centros.length" class="vacio">
        Todavía no hay centros clientes.
      </p>
      <table v-else class="administracion">
        <caption>{{ centros.length }} centro(s)</caption>
        <thead>
          <tr>
            <th scope="col">
              Centro
            </th>
            <th scope="col">
              RUC
            </th>
            <th scope="col">
              Alta
            </th>
            <th scope="col">
              Estado
            </th>
            <th scope="col">
              <span class="solo-lectores">Acciones</span>
            </th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="c in centros" :key="c.id">
            <td>
              <strong>{{ c.nombre_comercial || c.razon_social }}</strong>
              <span class="secundario-celda">{{ c.razon_social }} · {{ c.subdominio }}</span>
            </td>
            <td class="numero">
              {{ c.ruc }}
            </td>
            <td class="numero">
              {{ fecha(c.creado_en) }}
            </td>
            <td>
              <span class="etiqueta" :class="(ESTADOS[c.estado] ?? [])[1]">{{ (ESTADOS[c.estado] ?? [c.estado])[0] }}</span>
              <span v-if="c.estado === 'SUSPENDIDO' && c.motivo_suspension" class="secundario-celda">{{ c.motivo_suspension }}</span>
            </td>
            <td class="accion">
              <form v-if="suspendiendo === c.id" class="acciones-fila confirmacion" @submit.prevent="cambiarEstado(c, 'SUSPENDIDO')">
                <label class="solo-lectores" :for="`motivo-${c.id}`">Motivo de la suspensión</label>
                <input
                  :id="`motivo-${c.id}`"
                  ref="campoMotivo"
                  v-model="motivo"
                  class="campo-motivo"
                  maxlength="200"
                  placeholder="Motivo de la suspensión"
                  required
                >
                <button class="boton-fila" type="submit" :disabled="!motivo.trim()">
                  Suspender
                </button>
                <button class="secundario boton-fila" type="button" @click="suspendiendo = null">
                  No
                </button>
              </form>
              <div v-else class="acciones-fila">
                <button class="secundario boton-fila" type="button" :aria-label="`Editar ${c.nombre_comercial || c.razon_social}`" @click="abrir(c)">
                  Editar
                </button>
                <button
                  v-if="c.estado === 'SUSPENDIDO'"
                  class="secundario boton-fila"
                  type="button"
                  :aria-label="`Reactivar ${c.nombre_comercial || c.razon_social}`"
                  @click="cambiarEstado(c, 'ACTIVO')"
                >
                  Reactivar
                </button>
                <button
                  v-else
                  class="secundario boton-fila"
                  type="button"
                  :aria-label="`Suspender ${c.nombre_comercial || c.razon_social}`"
                  @click="pedirSuspension(c)"
                >
                  Suspender
                </button>
              </div>
            </td>
          </tr>
        </tbody>
      </table>
    </section>

    <dialog ref="dialogo" class="dialogo" aria-labelledby="titulo-centro">
      <form method="dialog" class="dialogo-cabecera">
        <h2 id="titulo-centro">
          {{ editando ? `Editar ${editando.nombre_comercial || editando.razon_social}` : 'Nuevo centro cliente' }}
        </h2>
        <button class="enlace" type="submit" aria-label="Cerrar">
          ×
        </button>
      </form>
      <form class="dialogo-cuerpo" @submit.prevent="guardar">
        <div class="fila-campos">
          <div class="campo">
            <label for="ce-ruc">RUC *</label>
            <input id="ce-ruc" ref="primerCampo" v-model="formulario.ruc" maxlength="11" inputmode="numeric" required :aria-invalid="'ruc' in camposConError">
          </div>
          <div class="campo">
            <label for="ce-comercial">Nombre comercial *</label>
            <input id="ce-comercial" v-model="formulario.nombre_comercial" maxlength="100" required :aria-invalid="'nombre_comercial' in camposConError">
          </div>
        </div>
        <div class="campo">
          <label for="ce-razon">Razón social *</label>
          <input id="ce-razon" v-model="formulario.razon_social" maxlength="150" required :aria-invalid="'razon_social' in camposConError">
        </div>
        <div class="fila-campos">
          <div class="campo">
            <label for="ce-subdominio">Subdominio *</label>
            <input id="ce-subdominio" v-model="formulario.subdominio" maxlength="40" required :aria-invalid="'subdominio' in camposConError">
          </div>
          <div class="campo">
            <label for="ce-correo">Correo de contacto *</label>
            <input id="ce-correo" v-model="formulario.correo_contacto" type="email" maxlength="150" required :aria-invalid="'correo_contacto' in camposConError">
          </div>
        </div>

        <fieldset v-if="!editando" class="campo opciones">
          <legend>Administrador inicial del centro *</legend>
          <div class="fila-campos">
            <div class="campo">
              <label for="ad-nombres">Nombres *</label>
              <input id="ad-nombres" v-model="formulario.administrador.nombres" maxlength="80" required>
            </div>
            <div class="campo">
              <label for="ad-apellidos">Apellidos *</label>
              <input id="ad-apellidos" v-model="formulario.administrador.apellidos" maxlength="80" required>
            </div>
          </div>
          <div class="campo">
            <label for="ad-correo">Correo de acceso *</label>
            <input id="ad-correo" v-model="formulario.administrador.correo" type="email" required :aria-invalid="'administrador' in camposConError">
          </div>
          <p class="ayuda">
            Al guardar se genera una contraseña temporal que se muestra una sola vez.
          </p>
        </fieldset>

        <p v-if="errorFormulario" role="alert">
          {{ errorFormulario }}
        </p>
        <div class="dialogo-acciones">
          <button class="secundario" type="button" @click="dialogo.close()">
            Cancelar
          </button>
          <button type="submit" :disabled="!completo || guardando">
            {{ guardando ? 'Guardando…' : (editando ? 'Guardar cambios' : 'Crear centro') }}
          </button>
        </div>
      </form>
    </dialog>
  </main>
</template>
