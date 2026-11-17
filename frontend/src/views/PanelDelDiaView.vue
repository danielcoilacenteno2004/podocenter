<script setup>
// P04 Panel del día (CU04). La observación de la Práctica N.° 7 pedía
// segmentar el panel en lugar de apilar indicadores sueltos: cada bloque
// responde a una decisión distinta de la dueña del centro.
import { computed, ref, watch } from 'vue'
import { api } from '../services/api'
import { useSesion } from '../stores/sesion'
import { diaLargo, duracion, hora, hoy, moverDias, soles } from '../formato'
import { usarCifraAnimada } from '../composables/usarCifraAnimada'
import IconoTrazo from '../components/IconoTrazo.vue'
import TarjetaSeccion from '../components/TarjetaSeccion.vue'

const sesion = useSesion()
const panel = ref(null)
const fecha = ref(hoy())
const cargando = ref(false)
const error = ref(null)

const esHoy = computed(() => fecha.value === hoy())

const saludo = computed(() => {
  const h = new Date().getHours()
  const parte = h < 12 ? 'Buenos días' : h < 19 ? 'Buenas tardes' : 'Buenas noches'
  const nombre = sesion.usuario?.nombre_completo?.split(' ')[0]
  return nombre ? `${parte}, ${nombre}` : parte
})

// Las cifras principales se animan al cambiar de día.
const totalCitas = usarCifraAnimada(() => panel.value?.citas.total)
const esperado = usarCifraAnimada(() => panel.value?.ingresos.esperado)
const porcentaje = usarCifraAnimada(() => panel.value?.ocupacion.porcentaje)

const estadosConCitas = computed(() =>
  panel.value?.citas.por_estado.filter((fila) => fila.cantidad) ?? [])

const resumenEstados = computed(() => estadosConCitas.value.length
  ? estadosConCitas.value.map((fila) => `${fila.cantidad} ${fila.etiqueta.toLowerCase()}`).join(', ')
  : 'Sin citas en la jornada')

const proporcionConfirmada = computed(() => {
  const { esperado: total, confirmado } = panel.value?.ingresos ?? {}
  return Number(total) ? Math.round(Number(confirmado) * 100 / Number(total)) : 0
})

const montoMaximo = computed(() =>
  Math.max(...(panel.value?.ingresos.por_servicio.map((fila) => Number(fila.monto)) ?? []), 0))

// Si se cambia de día varias veces seguidas, solo cuenta la última respuesta:
// una más lenta no puede pisar a la del día que se está viendo.
let ultimaConsulta = 0
async function cargar () {
  if (!fecha.value) return
  const consulta = ++ultimaConsulta
  cargando.value = true
  error.value = null
  try {
    const { data } = await api.get('/panel/', { params: { fecha: fecha.value } })
    if (consulta === ultimaConsulta) panel.value = data
  } catch (problema) {
    if (consulta !== ultimaConsulta) return
    error.value = problema.mensaje
    panel.value = null
  } finally {
    if (consulta === ultimaConsulta) cargando.value = false
  }
}

watch(fecha, cargar, { immediate: true })
</script>

<template>
  <main>
    <header class="encabezado encabezado-con-accion">
      <div>
        <p class="saludo">{{ saludo }}</p>
        <h1>Panel del día</h1>
        <p class="dia">
          {{ diaLargo(fecha) }}<template v-if="panel?.sede"> · {{ panel.sede.nombre }}</template>
        </p>
      </div>

      <div class="navegar-dia" role="group" aria-label="Día del panel">
        <button class="secundario boton-fila boton-icono" type="button" aria-label="Día anterior" @click="fecha = moverDias(fecha, -1)">
          <IconoTrazo nombre="anterior" />
        </button>
        <label for="fecha" class="solo-lectores">Día</label>
        <input id="fecha" v-model="fecha" type="date" required>
        <button class="secundario boton-fila boton-icono" type="button" aria-label="Día siguiente" @click="fecha = moverDias(fecha, 1)">
          <IconoTrazo nombre="siguiente" />
        </button>
        <button class="secundario boton-fila" type="button" :disabled="esHoy" @click="fecha = hoy()">
          Hoy
        </button>
      </div>
    </header>

    <Transition name="aparecer">
      <p v-if="error" role="alert">{{ error }}</p>
    </Transition>

    <!-- Primera carga: esqueleto con la forma de los tres segmentos. -->
    <div v-if="!panel && cargando" class="segmentos" aria-hidden="true">
      <div v-for="n in 3" :key="n" class="tarjeta">
        <span class="esqueleto esqueleto-titulo" />
        <span class="esqueleto esqueleto-cifra" />
        <span class="esqueleto esqueleto-barra" />
        <span class="esqueleto esqueleto-linea" />
      </div>
    </div>
    <p v-if="cargando" class="solo-lectores" role="status">Cargando el panel…</p>

    <!-- Al cambiar de día se conservan las cifras anteriores, atenuadas, hasta
         que llegan las nuevas: la página no parpadea ni cambia de alto. -->
    <div v-if="panel" class="segmentos" :class="{ actualizando: cargando }" :aria-busy="cargando">
      <!-- ---------------------------------------------------------- CITAS -->
      <TarjetaSeccion icono="calendario" :titulo="panel.citas.titulo">
        <template #acciones>
          <router-link class="enlace-flecha" :to="{ name: 'agenda', query: { fecha } }">
            Abrir la agenda <IconoTrazo nombre="flecha" :tamano="15" />
          </router-link>
        </template>

        <p class="cifra">
          <strong>{{ Math.round(totalCitas) }}</strong> cita(s) en la jornada
        </p>
        <p class="cifra-detalle">{{ panel.citas.pendientes }} por atender</p>

        <div class="reparto" role="img" :aria-label="`Reparto por estado: ${resumenEstados}`">
          <span
            v-for="fila in estadosConCitas"
            :key="fila.estado"
            :class="fila.estado"
            :style="{ flexGrow: fila.cantidad }"
          />
        </div>
        <ul class="conteos">
          <li v-for="fila in panel.citas.por_estado" :key="fila.estado">
            <span class="etiqueta" :class="fila.estado">{{ fila.etiqueta }}</span>
            <b>{{ fila.cantidad }}</b>
          </li>
        </ul>

        <router-link
          v-if="panel.citas.proxima"
          class="proxima"
          :to="{ name: 'agenda', query: { fecha } }"
        >
          <span class="proxima-hora">{{ hora(panel.citas.proxima.hora) }}</span>
          <span class="proxima-datos">
            <small>Próxima cita</small>
            <strong>{{ panel.citas.proxima.paciente }}</strong>
            <span>{{ panel.citas.proxima.servicio }} · {{ panel.citas.proxima.profesional }}</span>
          </span>
          <IconoTrazo class="proxima-flecha" nombre="flecha" />
        </router-link>
        <p v-else-if="panel.citas.pendientes" class="recuadro recuadro-con-icono tono-aviso">
          <IconoTrazo nombre="reloj" />
          {{ panel.citas.pendientes }} cita(s) programada(s) ya pasaron de hora sin registrar su atención.
        </p>
        <p v-else class="recuadro recuadro-con-icono">
          <IconoTrazo nombre="hecho" />
          {{ esHoy ? 'No quedan citas por atender hoy.' : 'No hay citas por atender ese día.' }}
        </p>
      </TarjetaSeccion>

      <!-- ------------------------------------------------------- INGRESOS -->
      <TarjetaSeccion icono="billete" :titulo="panel.ingresos.titulo">
        <p class="cifra"><strong>{{ soles(esperado) }}</strong> esperados</p>
        <p class="cifra-detalle">
          {{ soles(panel.ingresos.confirmado) }} confirmados · {{ proporcionConfirmada }} %
        </p>
        <div class="progreso" role="img" :aria-label="`${proporcionConfirmada} por ciento del ingreso esperado ya confirmado`">
          <span :style="{ width: `${proporcionConfirmada}%` }" />
        </div>

        <dl class="minis">
          <div><dt>Ticket promedio</dt><dd>{{ soles(panel.ingresos.ticket_promedio) }}</dd></div>
          <div :class="{ perdido: Number(panel.ingresos.perdido) > 0 }">
            <dt>No concretado</dt><dd>{{ soles(panel.ingresos.perdido) }}</dd>
          </div>
        </dl>

        <template v-if="panel.ingresos.por_servicio.length">
          <h3 class="subtitulo-segmento">Por servicio</h3>
          <ul class="servicios">
            <li v-for="fila in panel.ingresos.por_servicio" :key="fila.servicio_id">
              <router-link :to="{ name: 'agenda', query: { fecha, servicio: fila.servicio_id } }">
                {{ fila.servicio }}
              </router-link>
              <span class="servicio-citas">{{ fila.citas }} cita(s)</span>
              <span class="servicio-monto">{{ soles(fila.monto) }}</span>
              <span class="servicio-barra" aria-hidden="true">
                <span :style="{ width: `${montoMaximo ? Number(fila.monto) * 100 / montoMaximo : 0}%` }" />
              </span>
            </li>
          </ul>
        </template>
        <template #pie>
          <p class="nota">
            <IconoTrazo nombre="info" :tamano="15" />
            <span>{{ panel.ingresos.nota }} Cada servicio abre la agenda del día filtrada por él.</span>
          </p>
        </template>
      </TarjetaSeccion>

      <!-- ------------------------------------------------------ OCUPACIÓN -->
      <TarjetaSeccion icono="reloj" :titulo="panel.ocupacion.titulo">
        <div v-if="panel.ocupacion.disponible" class="ocupacion">
          <div>
            <p class="cifra">
              <strong>{{ porcentaje.toFixed(1) }} %</strong> de la jornada vendida
            </p>
            <p class="cifra-detalle">Horario de la sede: {{ panel.ocupacion.horario }}</p>
          </div>
          <div>
            <div class="progreso progreso-grueso" role="img"
                 :aria-label="`${panel.ocupacion.porcentaje} por ciento de la jornada ocupada`">
              <span :style="{ width: `${Math.min(panel.ocupacion.porcentaje, 100)}%` }" />
            </div>
            <dl class="minis">
              <div><dt><span class="muestra agendado" aria-hidden="true" />Agendado</dt><dd>{{ duracion(panel.ocupacion.minutos_agendados) }}</dd></div>
              <div><dt><span class="muestra libre" aria-hidden="true" />Libre</dt><dd>{{ duracion(panel.ocupacion.libres) }}</dd></div>
            </dl>
          </div>
        </div>
        <p v-else class="recuadro recuadro-con-icono">
          <IconoTrazo nombre="cerrado" />
          {{ panel.ocupacion.detalle }}
        </p>
      </TarjetaSeccion>
    </div>
  </main>
</template>

<style scoped>
.saludo { margin: 0 0 .15rem; color: var(--tinta-suave); font-weight: 600; font-size: .92rem; }
.dia::first-letter { text-transform: uppercase; }
.encabezado-con-accion { align-items: flex-end; }
.navegar-dia input { width: auto; }
.boton-icono { display: grid; place-items: center; padding-inline: .5rem; }

.segmentos {
  display: grid;
  gap: 1.25rem;
  /* Citas e Ingresos comparten la primera fila; Ocupación ocupa el ancho
     completo debajo, porque su contenido es una barra y dos cifras. En celular
     los tres pasan a una sola columna. */
  grid-template-columns: repeat(2, minmax(0, 1fr));
  transition: opacity var(--transicion);
}
.segmentos > :nth-child(3) { grid-column: 1 / -1; }
.segmentos.actualizando { opacity: .55; }
.esqueleto-titulo { width: 40%; height: 1.4rem; }
.esqueleto-cifra { width: 55%; height: 2.4rem; margin-top: 1.25rem; }
.esqueleto-barra { width: 100%; height: .6rem; margin-top: 1.25rem; }
.esqueleto-linea { width: 75%; height: 1rem; margin-top: .9rem; }
@media (max-width: 780px) {
  .segmentos { grid-template-columns: 1fr; }
  .segmentos > :nth-child(3) { grid-column: auto; }
}

/* Las tarjetas del panel entran escalonadas. */
.segmentos > :nth-child(2) { animation-delay: 60ms; }
.segmentos > :nth-child(3) { animation-delay: 120ms; }


.cifra { margin: 0; color: var(--tinta-suave); }
.cifra strong {
  margin-right: .25rem; font-size: 2rem; line-height: 1.1; letter-spacing: -.02em;
  color: var(--tinta); font-variant-numeric: tabular-nums;
}
.cifra-detalle { margin: .2rem 0 1rem; font-size: .9rem; color: var(--tinta-suave); }

/* Reparto de la jornada por estado: cada tramo mide lo que su cantidad. */
.reparto {
  display: flex; gap: 3px; height: .6rem; margin-bottom: .85rem;
  border-radius: 999px; overflow: hidden; background: var(--fondo);
}
.reparto span { flex-basis: 0; background: var(--tono); transform-origin: left; animation: crecer .6s var(--transicion) both; }
.conteos { list-style: none; padding: 0; margin: 0 0 1.1rem; display: flex; gap: .4rem .9rem; flex-wrap: wrap; }
.conteos li { display: flex; align-items: center; gap: .35rem; }
.conteos b { font-variant-numeric: tabular-nums; }

.proxima {
  display: flex; align-items: center; gap: .85rem;
  padding: .75rem .9rem; border-radius: var(--radio);
  background: var(--marca-tenue); color: var(--tinta); text-decoration: none;
  border: 1px solid transparent; transition: border-color var(--transicion), background-color var(--transicion);
}
.proxima:hover { border-color: var(--oficial-claro); }
.proxima-hora {
  flex: none; padding: .45rem .6rem; border-radius: 8px;
  background: var(--marca); color: var(--blanco); font-weight: 700; font-size: .9rem;
  font-variant-numeric: tabular-nums;
}
.proxima-datos { display: grid; min-width: 0; line-height: 1.3; }
.proxima-datos small { font-size: .72rem; text-transform: uppercase; letter-spacing: .05em; color: var(--tinta-suave); font-weight: 700; }
.proxima-datos span { font-size: .85rem; color: var(--tinta-suave); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.proxima-flecha { margin-left: auto; flex: none; color: var(--marca); transition: transform var(--transicion); }
.proxima:hover .proxima-flecha { transform: translateX(3px); }


.progreso { height: .6rem; margin-bottom: 1.1rem; border-radius: 999px; background: var(--fondo); overflow: hidden; }
.progreso span {
  display: block; height: 100%; border-radius: inherit; background: var(--marca);
  transform-origin: left; animation: crecer .7s var(--transicion) both;
  transition: width .5s var(--transicion);
}
.progreso-grueso { height: .9rem; margin-bottom: .9rem; }

.minis { display: flex; gap: 2rem; margin: 0 0 1rem; }
.minis dt { display: flex; align-items: center; gap: .35rem; font-size: .78rem; color: var(--tinta-suave); font-weight: 600; }
.minis dd { margin: .1rem 0 0; font-size: 1.15rem; font-weight: 700; font-variant-numeric: tabular-nums; }
.minis .perdido dd { color: var(--alerta); }
.muestra { width: .6rem; height: .6rem; border-radius: 50%; }
.muestra.agendado { background: var(--marca); }
.muestra.libre { background: var(--borde); }

.subtitulo-segmento {
  margin: .25rem 0 .5rem; font-size: .74rem; text-transform: uppercase;
  letter-spacing: .06em; color: var(--tinta-suave);
}
.servicios { list-style: none; margin: 0; padding: 0; display: grid; gap: .65rem; }
.servicios li { display: grid; grid-template-columns: minmax(0, 1fr) auto auto; gap: .2rem .75rem; align-items: baseline; font-size: .92rem; }
.servicios a { font-weight: 600; color: var(--tinta); text-decoration: none; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.servicios a:hover { color: var(--marca); text-decoration: underline; }
.servicio-citas { font-size: .8rem; color: var(--tinta-suave); }
.servicio-monto { font-weight: 700; font-variant-numeric: tabular-nums; text-align: right; }
.servicio-barra { grid-column: 1 / -1; height: 4px; border-radius: 999px; background: var(--fondo); overflow: hidden; }
.servicio-barra span { display: block; height: 100%; background: var(--oficial-claro); transform-origin: left; animation: crecer .7s var(--transicion) both; }

.nota { margin: 0; display: flex; gap: .45rem; }
.nota svg { flex: none; margin-top: .1rem; }

.ocupacion { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1.6fr); gap: 1rem 2.5rem; align-items: center; }
.ocupacion .minis { margin: 0; }
@media (max-width: 780px) { .ocupacion { grid-template-columns: 1fr; } }

@keyframes crecer { from { transform: scaleX(0); } }
</style>
