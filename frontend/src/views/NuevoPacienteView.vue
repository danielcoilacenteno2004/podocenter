<script setup>
// P09 Registrar paciente (CU06, RF04, RNF06), según el wireframe y la Tabla
// 22 de la Práctica N.° 7. Paciente y consentimiento se guardan en una sola
// operación del servidor (registrar_paciente): no puede existir una ficha
// sin constancia de la base legal del tratamiento.
//
// Solo alta. La edición no existe todavía: el PATCH de /pacientes/ se quitó
// porque escribía sin auditoría. Por eso los antecedentes se piden aquí,
// aunque el wireframe los dejaba para la ficha: hoy no hay otro momento.
//
// Del wireframe no se construyen la evidencia firmada adjunta ni los
// canales separados (WhatsApp / correo): el modelo guarda una sola
// autorización de recordatorios. Las validaciones de formato de la Tabla 22
// (8 dígitos del DNI, celular de 9 dígitos, fecha no futura) no las aplica
// el servidor, y la pantalla no las inventa.
import { computed, nextTick, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '../services/api'

const router = useRouter()

const TIPOS = [['DNI', 'DNI'], ['CE', 'Carné de extranjería'], ['PAS', 'Pasaporte']]

const formulario = ref({
  tipo_documento: 'DNI', documento: '', nombres: '', apellidos: '',
  fecha_nacimiento: '', telefono: '', correo: '', antecedentes: ''
})
const consentimiento = ref({ acepta_tratamiento_datos: false, acepta_recordatorios: false })
const existente = ref(null)       // paciente con el mismo documento, si lo hay
const guardando = ref(false)
const error = ref(null)
const camposConError = ref({})
const campoTipo = ref(null)

// Sin el consentimiento de tratamiento de datos el servidor rechaza el alta
// (sin-consentimiento); la pantalla no ofrece guardar hasta tenerlo (RNF06).
const completo = computed(() => {
  const f = formulario.value
  return Boolean(f.documento.trim() && f.nombres.trim() && f.apellidos.trim() &&
    consentimiento.value.acepta_tratamiento_datos && !existente.value)
})

// «Avisa del duplicado antes de llenar el resto»: se consulta con la misma
// búsqueda de P08 y se compara tipo y número exactos. El servidor vuelve a
// comprobarlo al guardar (paciente-duplicado).
async function comprobarDocumento () {
  existente.value = null
  const documento = formulario.value.documento.trim()
  if (!documento) return
  try {
    const { data } = await api.get('/pacientes/', { params: { buscar: documento } })
    existente.value = (data.results ?? data).find((p) =>
      p.documento === documento && p.tipo_documento === formulario.value.tipo_documento) ?? null
  } catch {
    // Si la consulta falla, decide el servidor al guardar.
  }
}

async function guardar () {
  guardando.value = true
  error.value = null
  camposConError.value = {}
  try {
    const datos = { ...formulario.value, consentimiento: consentimiento.value }
    if (!datos.fecha_nacimiento) delete datos.fecha_nacimiento
    const { data } = await api.post('/pacientes/', datos)
    router.push({ name: 'ficha-paciente', params: { pacienteId: data.id }, query: { aviso: 'paciente-registrado' } })
  } catch (problema) {
    error.value = problema.mensaje
    camposConError.value = problema.campos ?? {}
  } finally {
    guardando.value = false
  }
}

onMounted(async () => {
  await nextTick()
  campoTipo.value?.focus()
})
</script>

<template>
  <main>
    <div class="encabezado">
      <router-link :to="{ name: 'pacientes' }">
        ← Volver a pacientes
      </router-link>
      <h1>Registrar paciente</h1>
    </div>

    <form class="tarjeta" aria-label="Datos del paciente" @submit.prevent="guardar">
      <div class="fila-campos fila-documento">
        <div class="campo">
          <label for="p-tipo">Tipo de documento *</label>
          <select id="p-tipo" ref="campoTipo" v-model="formulario.tipo_documento" @change="comprobarDocumento">
            <option v-for="[valor, etiqueta] in TIPOS" :key="valor" :value="valor">
              {{ etiqueta }}
            </option>
          </select>
        </div>
        <div class="campo">
          <label for="p-documento">N.° de documento *</label>
          <input
            id="p-documento"
            v-model="formulario.documento"
            maxlength="20"
            required
            autocomplete="off"
            :aria-invalid="Boolean(existente) || 'documento' in camposConError"
            aria-describedby="estado-documento"
            @blur="comprobarDocumento"
          >
          <p id="estado-documento" class="ayuda" role="status">
            <template v-if="existente">
              Ya existe: <router-link :to="{ name: 'ficha-paciente', params: { pacienteId: existente.id } }">
                {{ existente.apellidos }}, {{ existente.nombres }}
              </router-link>
            </template>
          </p>
        </div>
      </div>

      <div class="fila-campos">
        <div class="campo">
          <label for="p-nombres">Nombres *</label>
          <input id="p-nombres" v-model="formulario.nombres" maxlength="80" required :aria-invalid="'nombres' in camposConError">
        </div>
        <div class="campo">
          <label for="p-apellidos">Apellidos *</label>
          <input id="p-apellidos" v-model="formulario.apellidos" maxlength="80" required :aria-invalid="'apellidos' in camposConError">
        </div>
      </div>

      <div class="fila-campos fila-tres">
        <div class="campo">
          <label for="p-nacimiento">Fecha de nacimiento</label>
          <input id="p-nacimiento" v-model="formulario.fecha_nacimiento" type="date" :aria-invalid="'fecha_nacimiento' in camposConError">
        </div>
        <div class="campo">
          <label for="p-telefono">Teléfono</label>
          <input id="p-telefono" v-model="formulario.telefono" type="tel" maxlength="20" :aria-invalid="'telefono' in camposConError">
        </div>
        <div class="campo">
          <label for="p-correo">Correo electrónico</label>
          <input id="p-correo" v-model="formulario.correo" type="email" :aria-invalid="'correo' in camposConError">
        </div>
      </div>

      <div class="campo">
        <label for="p-antecedentes">Antecedentes clínicos</label>
        <textarea
          id="p-antecedentes"
          v-model="formulario.antecedentes"
          rows="3"
          placeholder="Diabetes, anticoagulantes, alergias…"
          aria-describedby="ayuda-antecedentes"
        />
        <p id="ayuda-antecedentes" class="ayuda">
          Se guardan cifrados. Por ahora no se pueden corregir después del alta.
        </p>
      </div>

      <fieldset class="campo opciones consentimiento-alta">
        <legend>Consentimiento informado (Ley N.° 29733) *</legend>
        <label>
          <input v-model="consentimiento.acepta_tratamiento_datos" type="checkbox">
          <span>El paciente leyó y acepta el tratamiento de sus datos de salud.</span>
        </label>
        <label>
          <input v-model="consentimiento.acepta_recordatorios" type="checkbox">
          <span>Autoriza recibir recordatorios de sus citas.</span>
        </label>
        <p v-if="!consentimiento.acepta_tratamiento_datos" class="ayuda">
          Sin este consentimiento no se puede registrar al paciente.
        </p>
      </fieldset>

      <p v-if="error" role="alert">
        {{ error }}
      </p>

      <div class="dialogo-acciones">
        <router-link class="boton-secundario" :to="{ name: 'pacientes' }">
          Cancelar
        </router-link>
        <button type="submit" :disabled="!completo || guardando">
          {{ guardando ? 'Guardando…' : 'Guardar paciente' }}
        </button>
      </div>
    </form>
  </main>
</template>
