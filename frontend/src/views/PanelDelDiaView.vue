<script setup>
// P04 Panel del día (CU04). La observación de la Práctica N.° 7 pedía
// segmentar el panel en lugar de apilar indicadores sueltos: cada bloque
// responde a una decisión distinta de la dueña del centro.
import { onMounted, ref } from 'vue'
import { api } from '../services/api'
import { useSesion } from '../stores/sesion'

const sesion = useSesion()
const panel = ref(null)
// Fecha local (AAAA-MM-DD): toISOString() da la de UTC, que en Perú ya es
// el día siguiente desde las 19:00.
const fecha = ref(new Date().toLocaleDateString('en-CA'))
const cargando = ref(false)
const error = ref(null)

function hora (valor) {
  return new Date(valor).toLocaleTimeString('es-PE', { hour: '2-digit', minute: '2-digit' })
}

async function cargar () {
  cargando.value = true
  error.value = null
  try {
    const { data } = await api.get('/panel/', { params: { fecha: fecha.value } })
    panel.value = data
  } catch (problema) {
    error.value = problema.mensaje
    panel.value = null
  } finally {
    cargando.value = false
  }
}

onMounted(cargar)
</script>

<template>
  <main>
    <div class="encabezado">
      <h1>Panel del día</h1>
      <p>
        {{ new Date(fecha + 'T12:00').toLocaleDateString('es-PE',
           { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' }) }}
        <template v-if="panel?.sede"> · {{ panel.sede.nombre }}</template>
      </p>
    </div>

    <form class="filtros" @submit.prevent="cargar">
      <div class="campo">
        <label for="fecha">Día</label>
        <input id="fecha" v-model="fecha" type="date" @change="cargar">
      </div>
    </form>

    <p v-if="error" role="alert">{{ error }}</p>
    <p v-if="cargando" role="status">Cargando el panel…</p>

    <div v-else-if="panel" class="segmentos">
      <!-- ---------------------------------------------------------- CITAS -->
      <section class="segmento tarjeta" aria-labelledby="seg-citas">
        <h2 id="seg-citas">{{ panel.citas.titulo }}</h2>
        <p class="resumen">
          <strong>{{ panel.citas.total }}</strong> cita(s) en la jornada ·
          {{ panel.citas.pendientes }} por atender
        </p>

        <ul class="conteos">
          <li v-for="fila in panel.citas.por_estado" :key="fila.estado">
            <span class="etiqueta" :class="fila.estado">{{ fila.etiqueta }}</span>
            <b>{{ fila.cantidad }}</b>
          </li>
        </ul>

        <router-link v-if="panel.citas.proxima" class="destacado"
                     :to="{ name: 'agenda', query: { fecha } }">
          Próxima: <strong>{{ hora(panel.citas.proxima.hora) }}</strong> —
          {{ panel.citas.proxima.paciente }} ({{ panel.citas.proxima.servicio }})
        </router-link>
        <p v-else class="vacio" style="padding:.5rem 0">
          No quedan citas por atender hoy.
        </p>

        <router-link :to="{ name: 'agenda' }">Abrir la agenda</router-link>
      </section>

      <!-- ------------------------------------------------------- INGRESOS -->
      <section class="segmento tarjeta" aria-labelledby="seg-ingresos">
        <h2 id="seg-ingresos">{{ panel.ingresos.titulo }}</h2>
        <p class="resumen">
          <strong>S/ {{ panel.ingresos.esperado }}</strong> esperados ·
          S/ {{ panel.ingresos.confirmado }} confirmados
        </p>

        <dl class="minis">
          <div><dt>Ticket promedio</dt><dd>S/ {{ panel.ingresos.ticket_promedio }}</dd></div>
          <div><dt>No concretado</dt><dd>S/ {{ panel.ingresos.perdido }}</dd></div>
        </dl>

        <table v-if="panel.ingresos.por_servicio.length">
          <caption>Por servicio</caption>
          <thead>
            <tr><th scope="col">Servicio</th><th scope="col">Citas</th><th scope="col">Monto</th></tr>
          </thead>
          <tbody>
            <tr v-for="fila in panel.ingresos.por_servicio" :key="fila.servicio_id">
              <td>
                <router-link :to="{ name: 'agenda',
                                    query: { fecha, servicio: fila.servicio_id } }">
                  {{ fila.servicio }}
                </router-link>
              </td>
              <td class="numero">{{ fila.citas }}</td>
              <td class="numero">S/ {{ fila.monto }}</td>
            </tr>
          </tbody>
        </table>
        <p class="nota">
          {{ panel.ingresos.nota }}
          Cada servicio abre la agenda del día filtrada por él.
        </p>
      </section>

      <!-- ------------------------------------------------------ OCUPACIÓN -->
      <section class="segmento tarjeta" aria-labelledby="seg-ocupacion">
        <h2 id="seg-ocupacion">{{ panel.ocupacion.titulo }}</h2>

        <template v-if="panel.ocupacion.disponible">
          <p class="resumen">
            <strong>{{ panel.ocupacion.porcentaje }} %</strong> de la jornada vendida
          </p>
          <div class="barra-ocupacion" role="img"
               :aria-label="`${panel.ocupacion.porcentaje} por ciento de la jornada ocupada`">
            <span :style="{ width: Math.min(panel.ocupacion.porcentaje, 100) + '%' }"></span>
          </div>
          <dl class="minis">
            <div><dt>Agendado</dt><dd>{{ panel.ocupacion.minutos_agendados }} min</dd></div>
            <div><dt>Libre</dt><dd>{{ panel.ocupacion.libres }} min</dd></div>
          </dl>
          <p class="nota">Horario de la sede: {{ panel.ocupacion.horario }}.</p>
        </template>
        <p v-else class="vacio" style="padding:1rem 0">{{ panel.ocupacion.detalle }}</p>
      </section>

    </div>
  </main>
</template>

<style scoped>
.segmentos {
  display: grid;
  gap: 1.25rem;
  /* Citas e Ingresos comparten la primera fila; Ocupación ocupa el ancho
     completo debajo, porque su contenido es una barra y dos cifras. En celular
     los tres pasan a una sola columna. */
  grid-template-columns: repeat(2, minmax(0, 1fr));
}
.segmentos > section:nth-child(3) { grid-column: 1 / -1; }
@media (max-width: 780px) {
  .segmentos { grid-template-columns: 1fr; }
  .segmentos > section:nth-child(3) { grid-column: auto; }
}
.segmento h2 { display: flex; align-items: center; gap: .6rem; }
.resumen { margin: 0 0 1rem; font-size: 1.05rem; color: var(--tinta-suave); }
.resumen strong { font-size: 1.7rem; color: var(--tinta); font-variant-numeric: tabular-nums; }

.conteos { list-style: none; padding: 0; margin: 0 0 1rem; display: flex; gap: .5rem; flex-wrap: wrap; }
.conteos li { display: flex; align-items: center; gap: .4rem; }
.conteos b { font-variant-numeric: tabular-nums; }

.minis { display: flex; gap: 1.75rem; margin: 0 0 1rem; }
.minis dt { font-size: .78rem; color: var(--tinta-suave); font-weight: 600; }
.minis dd { margin: 0; font-size: 1.15rem; font-weight: 700; font-variant-numeric: tabular-nums; }

.destacado {
  display: block; text-decoration: none;
  background: var(--marca-tenue); color: var(--marca-oscura);
  padding: .6rem .8rem; border-radius: 8px; margin: 0 0 1rem;
}
.destacado:hover { background: #d8eae9; }
.nota { font-size: .82rem; color: var(--tinta-suave); margin: .75rem 0 0; }

.barra-ocupacion {
  height: 10px; border-radius: 999px; background: var(--fondo);
  border: 1px solid var(--borde); overflow: hidden; margin-bottom: 1rem;
}
.barra-ocupacion span { display: block; height: 100%; background: var(--marca); }

</style>
