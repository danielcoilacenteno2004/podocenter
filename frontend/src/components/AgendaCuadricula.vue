<script setup>
// P05, vista de cuadrícula (Práctica N.° 7, Figura 3): una fila por hora y
// una columna por profesional de la sede, para «ver el día completo de un
// golpe de vista». Se mantiene junto a la vista de lista (Figura 4).
//
// Solo pinta. Las citas llegan ya filtradas por el servidor; las filas salen
// del horario de la sede que devuelve la agenda; y los huecos que se ofrecen
// son los que el servidor aceptaría por horario y por no estar en el pasado.
// El solapamiento lo sigue decidiendo `programar_cita`.
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'

const props = defineProps({
  fecha: { type: String, required: true },
  citas: { type: Array, default: () => [] },
  // [{ id, nombre }] en el orden en que se dibujan las columnas
  profesionales: { type: Array, default: () => [] },
  // { apertura: 'HH:MM', cierre: 'HH:MM' } o null si la sede no abre
  horario: { type: Object, default: null },
  etiquetas: { type: Object, default: () => ({}) },
  // Mientras llega la jornada nueva no se ofrecen huecos: se calcularían con
  // las citas de antes y podrían mostrar libre lo que ya está ocupado.
  actualizando: { type: Boolean, default: false }
})
const emit = defineEmits(['hueco', 'elegir'])

const PIXELES_POR_MINUTO = 1.2
const PASO_DEL_HUECO = 30

function minutosDe (texto) {
  const [h, m] = texto.split(':').map(Number)
  return h * 60 + m
}
function minutosDelDia (valor) {
  const d = new Date(valor)
  return d.getHours() * 60 + d.getMinutes()
}
function textoDe (minutos) {
  return `${String(Math.floor(minutos / 60)).padStart(2, '0')}:${String(minutos % 60).padStart(2, '0')}`
}

// El rango cubre el horario de la sede y, si alguna cita quedó fuera de él
// (la demostración crea citas «en curso» a cualquier hora), también esa cita:
// la cuadrícula nunca esconde una cita que la lista sí muestra.
const rango = computed(() => {
  let desde = props.horario ? minutosDe(props.horario.apertura) : Infinity
  let hasta = props.horario ? minutosDe(props.horario.cierre) : -Infinity
  for (const cita of props.citas) {
    desde = Math.min(desde, minutosDelDia(cita.inicio))
    hasta = Math.max(hasta, minutosDelDia(cita.fin) || 24 * 60)
  }
  if (!Number.isFinite(desde)) return null
  return { desde: Math.floor(desde / 60) * 60, hasta: Math.min(24 * 60, Math.ceil(hasta / 60) * 60) }
})

const horas = computed(() => {
  if (!rango.value) return []
  const lista = []
  for (let m = rango.value.desde; m < rango.value.hasta; m += 60) lista.push(m)
  return lista
})
const alto = computed(() => rango.value ? (rango.value.hasta - rango.value.desde) * PIXELES_POR_MINUTO : 0)

// Dentro de una columna solo pueden cruzarse una cancelada y su reemplazo
// (la base impide el resto). Se reparten en carriles para que no se tapen.
const columnas = computed(() => props.profesionales.map((p) => {
  const propias = props.citas
    .filter((c) => c.profesional === p.id)
    .sort((a, b) => new Date(a.inicio) - new Date(b.inicio))
  const finDeCarril = []
  const bloques = propias.map((cita) => {
    const inicio = new Date(cita.inicio).getTime()
    let carril = finDeCarril.findIndex((fin) => fin <= inicio)
    if (carril === -1) carril = finDeCarril.push(0) - 1
    finDeCarril[carril] = new Date(cita.fin).getTime()
    return { cita, carril }
  })
  return { ...p, bloques, carriles: Math.max(1, finDeCarril.length) }
}))

function estiloDe ({ cita, carril }, carriles) {
  const inicio = minutosDelDia(cita.inicio)
  const duracion = (new Date(cita.fin) - new Date(cita.inicio)) / 60000
  return {
    top: `${(inicio - rango.value.desde) * PIXELES_POR_MINUTO}px`,
    height: `${Math.max(duracion * PIXELES_POR_MINUTO, 26)}px`,
    left: `calc(${(100 / carriles) * carril}% + 2px)`,
    width: `calc(${100 / carriles}% - 4px)`
  }
}

// Reloj de la pantalla: mueve la línea de «ahora» y retira los huecos que
// van quedando en el pasado sin recargar la agenda.
const ahora = ref(new Date())
let reloj = null
onMounted(() => { reloj = setInterval(() => { ahora.value = new Date() }, 60000) })
onBeforeUnmount(() => clearInterval(reloj))

const esHoy = computed(() => props.fecha === ahora.value.toLocaleDateString('en-CA'))
const lineaDeAhora = computed(() => {
  if (!esHoy.value || !rango.value) return null
  const m = ahora.value.getHours() * 60 + ahora.value.getMinutes()
  if (m < rango.value.desde || m >= rango.value.hasta) return null
  return `${(m - rango.value.desde) * PIXELES_POR_MINUTO}px`
})

// Huecos que se pueden pulsar: dentro del horario, con los 15 minutos de
// anticipación que exige `programar_cita` (cita-en-el-pasado) y sin una cita
// vigente encima. Las canceladas no ocupan el hueco. Que el servicio elegido
// quepa antes del cierre lo sigue diciendo el servidor (fuera-de-horario).
const ANTICIPACION_MINIMA = 15
const huecos = computed(() => {
  if (props.actualizando || !props.horario ||
      props.fecha < ahora.value.toLocaleDateString('en-CA')) return {}
  const apertura = minutosDe(props.horario.apertura)
  const cierre = minutosDe(props.horario.cierre)
  const minutoActual = esHoy.value ? ahora.value.getHours() * 60 + ahora.value.getMinutes() : -1
  const porProfesional = {}
  for (const columna of columnas.value) {
    const ocupado = columna.bloques
      .filter(({ cita }) => cita.estado !== 'CANCELADA')
      .map(({ cita }) => [minutosDelDia(cita.inicio), minutosDelDia(cita.fin)])
    const lista = []
    for (let m = apertura; m + PASO_DEL_HUECO <= cierre; m += PASO_DEL_HUECO) {
      if (esHoy.value && m < minutoActual + ANTICIPACION_MINIMA) continue
      if (ocupado.some(([i, f]) => m < f && m + PASO_DEL_HUECO > i)) continue
      lista.push(m)
    }
    porProfesional[columna.id] = lista
  }
  return porProfesional
})

// En el bloque cabe poco: hora de 24 h, como la regla de la izquierda.
function hora (valor) {
  return textoDe(minutosDelDia(valor))
}
</script>

<template>
  <div>
    <p v-if="!rango" class="vacio">
      La sede no atiende este día y no hay citas registradas.
    </p>
    <p v-else-if="!profesionales.length" class="vacio">
      No hay profesionales asignadas a esta sede.
    </p>
    <template v-else>
      <p v-if="!horario" class="ayuda">
        La sede no atiende este día; se muestran solo las citas ya registradas.
      </p>
      <div class="cuadricula-marco">
        <div
          class="cuadricula"
          :style="{ '--columnas': profesionales.length }"
          role="region"
          :aria-label="`Agenda del ${fecha} por hora y profesional`"
        >
          <div class="esquina" />
          <div v-for="columna in columnas" :key="columna.id" class="cabeza">
            {{ columna.nombre }}
          </div>

          <div class="regla" :style="{ height: `${alto}px` }" aria-hidden="true">
            <span v-for="m in horas" :key="m" :style="{ top: `${(m - rango.desde) * PIXELES_POR_MINUTO}px` }">
              {{ textoDe(m) }}
            </span>
          </div>

          <div
            v-for="columna in columnas"
            :key="`col-${columna.id}`"
            class="columna"
            :style="{ height: `${alto}px`, '--hora': `${60 * PIXELES_POR_MINUTO}px` }"
          >
            <button
              v-for="m in huecos[columna.id] ?? []"
              :key="`h-${m}`"
              type="button"
              class="hueco"
              :style="{ top: `${(m - rango.desde) * PIXELES_POR_MINUTO}px`, height: `${PASO_DEL_HUECO * PIXELES_POR_MINUTO}px` }"
              :aria-label="`Nueva cita a las ${textoDe(m)} con ${columna.nombre}`"
              @click="emit('hueco', { hora: textoDe(m), profesional: columna.id })"
            >
              <span>+ {{ textoDe(m) }}</span>
            </button>

            <button
              v-for="bloque in columna.bloques"
              :key="bloque.cita.id"
              type="button"
              class="bloque"
              :class="bloque.cita.estado"
              :style="estiloDe(bloque, columna.carriles)"
              :aria-label="`${hora(bloque.cita.inicio)}, ${bloque.cita.paciente_nombre}, ${bloque.cita.servicio_nombre}, ${etiquetas[bloque.cita.estado] ?? bloque.cita.estado}`"
              @click="emit('elegir', bloque.cita)"
            >
              <strong>{{ hora(bloque.cita.inicio) }} {{ bloque.cita.paciente_nombre }}</strong>
              <span>{{ bloque.cita.servicio_nombre }}</span>
            </button>

            <div v-if="lineaDeAhora" class="ahora" :style="{ top: lineaDeAhora }" aria-hidden="true" />
          </div>
        </div>
      </div>
      <ul class="leyenda" aria-label="Leyenda">
        <li v-for="(texto, estado) in etiquetas" :key="estado">
          <span class="muestra" :class="estado" /> {{ texto }}
        </li>
        <li class="ayuda">
          Los huecos libres se pulsan para crear una cita.
        </li>
      </ul>
    </template>
  </div>
</template>

<style scoped>
.cuadricula-marco { overflow-x: auto; }
.cuadricula {
  display: grid;
  grid-template-columns: 3.5rem repeat(var(--columnas), minmax(9rem, 1fr));
  min-width: calc(3.5rem + var(--columnas) * 9rem);
}
.esquina, .cabeza {
  position: sticky;
  top: 0;
  background: var(--superficie);
  border-bottom: 1px solid var(--borde);
  padding: .4rem .5rem;
  font-weight: 600;
  font-size: .9rem;
  z-index: 3;
}
.regla { position: relative; }
.regla span {
  position: absolute;
  right: .4rem;
  transform: translateY(-.55em);
  font-size: .75rem;
  color: var(--tinta-suave);
  font-variant-numeric: tabular-nums;
}
.regla span:first-child { transform: none; }
.columna {
  position: relative;
  border-left: 1px solid var(--borde);
  background-image: repeating-linear-gradient(
    to bottom, var(--borde) 0 1px, transparent 1px var(--hora));
}
.hueco {
  position: absolute;
  left: 2px;
  right: 2px;
  margin: 0;
  padding: 0 .4rem;
  border: 1px dashed transparent;
  border-radius: 6px;
  background: transparent;
  color: transparent;
  font-size: .75rem;
  text-align: left;
  cursor: pointer;
  z-index: 1;
}
.hueco:hover, .hueco:focus-visible {
  border-color: var(--marca);
  background: var(--marca-tenue);
  color: var(--marca-oscura);
}
.bloque {
  position: absolute;
  margin: 0;
  padding: .2rem .4rem;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 0;
  border-radius: 6px;
  border: 1px solid var(--marca);
  border-left-width: 4px;
  background: var(--marca-tenue);
  color: var(--tinta);
  font-size: .78rem;
  line-height: 1.25;
  text-align: left;
  cursor: pointer;
  z-index: 2;
}
.bloque strong, .bloque span {
  max-width: 100%;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  font-weight: 600;
}
.bloque span { font-weight: 400; color: var(--tinta-suave); }
.bloque.ATENDIDA { border-color: var(--ok); background: var(--ok-tenue); }
.bloque.NO_ASISTIO { border-color: var(--aviso); border-style: dashed; background: var(--aviso-tenue); }
.bloque.CANCELADA { border-color: var(--alerta); background: var(--alerta-tenue); opacity: .7; text-decoration: line-through; }
.bloque:focus-visible { outline: 3px solid var(--marca-oscura); outline-offset: 1px; }
.ahora {
  position: absolute;
  left: 0;
  right: 0;
  border-top: 2px solid var(--alerta);
  pointer-events: none;
  z-index: 2;
}
.leyenda {
  display: flex;
  flex-wrap: wrap;
  gap: .4rem 1rem;
  list-style: none;
  padding: 0;
  margin: .75rem 0 0;
  font-size: .85rem;
}
.muestra {
  display: inline-block;
  width: .9rem;
  height: .9rem;
  border-radius: 3px;
  vertical-align: -2px;
  border: 1px solid var(--marca);
  background: var(--marca-tenue);
}
.muestra.ATENDIDA { border-color: var(--ok); background: var(--ok-tenue); }
.muestra.NO_ASISTIO { border-color: var(--aviso); border-style: dashed; background: var(--aviso-tenue); }
.muestra.CANCELADA { border-color: var(--alerta); background: var(--alerta-tenue); }
</style>
