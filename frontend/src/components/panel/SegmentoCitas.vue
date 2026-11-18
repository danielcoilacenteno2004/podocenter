<script setup>
// Segmento «Citas» del panel del día (Práctica N.° 7, Tabla 7): el total y
// el conteo por estado, lo que viene —con la próxima cita destacada— y lo que
// falta registrar. El día completo está en la agenda; aquí va lo que se mira
// para saber a quién toca y qué hay que hacer.
import { computed } from 'vue'
import { hora, hoy } from '../../formato'
import IconoTrazo from '../IconoTrazo.vue'
import TarjetaSeccion from '../TarjetaSeccion.vue'

const props = defineProps({
  citas: { type: Object, required: true },
  fecha: { type: String, required: true }
})

const restantes = computed(() => props.citas.por_atender - props.citas.siguientes.length)
const hayProxima = computed(() => props.citas.siguientes.some((cita) => cita.momento === 'proxima'))
const esHoy = computed(() => props.fecha === hoy())

const agenda = computed(() => ({ name: 'agenda', query: { fecha: props.fecha } }))
const registrar = (cita) => ({ name: 'registrar-atencion', params: { citaId: cita.cita_id } })
const ficha = (cita) => ({ name: 'ficha-paciente', params: { pacienteId: cita.paciente_id } })
</script>

<template>
  <TarjetaSeccion icono="calendario" :titulo="citas.titulo" descripcion="Qué sigue y qué falta registrar">
    <!-- Total y conteo por estado en una sola línea; los estados en cero se
         atenúan, pero se ven, como pide la Tabla 7. -->
    <p class="estados">
      <strong>{{ citas.total }} cita(s)</strong>
      <span v-for="fila in citas.por_estado" :key="fila.estado" :class="[fila.estado, { cero: !fila.cantidad }]">
        <span class="punto" aria-hidden="true" />{{ fila.etiqueta }} <b>{{ fila.cantidad }}</b>
      </span>
    </p>

    <template v-if="citas.siguientes.length">
      <h3 class="titulo-grupo">A continuación</h3>
      <ol class="lista-citas siguientes">
        <li v-for="cita in citas.siguientes" :key="cita.cita_id" :class="cita.momento">
          <span class="hora">{{ hora(cita.inicio) }}</span>
          <span class="datos">
            <router-link :to="ficha(cita)" class="paciente">{{ cita.paciente }}</router-link>
            <small>{{ cita.servicio }} · {{ cita.profesional }}</small>
          </span>
          <!-- La que ya empezó se puede registrar desde aquí; la próxima abre la
               agenda de ese día (Tabla 7). -->
          <router-link
            v-if="cita.momento === 'en-curso'"
            class="enlace-flecha"
            :to="registrar(cita)"
            :aria-label="`Registrar la atención de ${cita.paciente}, en curso`"
          >
            En curso · Registrar <IconoTrazo nombre="flecha" :tamano="14" />
          </router-link>
          <router-link
            v-else-if="cita.momento === 'proxima'"
            class="enlace-flecha"
            :to="agenda"
            :aria-label="`Próxima cita: ${cita.paciente}. Abrir la agenda del día`"
          >
            Próxima <IconoTrazo nombre="flecha" :tamano="14" />
          </router-link>
        </li>
      </ol>
      <p v-if="!hayProxima" class="ayuda">No quedan citas por empezar después de las que están en curso.</p>
      <router-link v-if="restantes > 0" class="mas" :to="agenda">
        y {{ restantes }} más en la agenda
      </router-link>
    </template>

    <!-- Las citas cuya hora ya terminó sin registrar la atención se listan una
         por una, con su enlace: cada una que falta deja mal el ingreso del día
         y sin descontar los insumos del stock. -->
    <section v-if="citas.sin_registrar.length" class="recuadro tono-aviso" aria-labelledby="titulo-sin-registrar">
      <h3 id="titulo-sin-registrar">Sin registrar ({{ citas.sin_registrar.length }})</h3>
      <ul class="lista-citas">
        <li v-for="cita in citas.sin_registrar" :key="cita.cita_id">
          <span class="hora">{{ hora(cita.inicio) }}</span>
          <span class="datos">
            <router-link :to="ficha(cita)" class="paciente">{{ cita.paciente }}</router-link>
            <small>{{ cita.servicio }} · {{ cita.profesional }}</small>
          </span>
          <router-link class="enlace-flecha" :to="registrar(cita)" :aria-label="`Registrar la atención de ${cita.paciente}`">
            Registrar <IconoTrazo nombre="flecha" :tamano="14" />
          </router-link>
        </li>
      </ul>
    </section>

    <p v-if="!citas.siguientes.length && !citas.sin_registrar.length" class="recuadro recuadro-con-icono">
      <IconoTrazo nombre="hecho" />
      <template v-if="!citas.total">No hay citas en la jornada.</template>
      <template v-else>{{ esHoy ? 'No quedan citas por atender hoy.' : 'No quedan citas por atender ese día.' }}</template>
    </p>

    <template #pie>
      <router-link class="enlace-flecha" :to="agenda">
        Abrir la agenda del día <IconoTrazo nombre="flecha" :tamano="15" />
      </router-link>
    </template>
  </TarjetaSeccion>
</template>

<style scoped>
.estados { margin: 0 0 1.1rem; display: flex; flex-wrap: wrap; align-items: center; gap: .35rem 1.1rem; font-size: .88rem; color: var(--tinta-suave); }
.estados strong { color: var(--tinta); }
.estados > span { display: flex; align-items: center; gap: .4rem; }
.estados b { color: var(--tinta); font-variant-numeric: tabular-nums; }
.estados .cero { opacity: .5; }
.punto { width: .5rem; height: .5rem; border-radius: 50%; background: var(--tono); }

/* Fila de una cita: hora, paciente con servicio y profesional, y acción. */
.lista-citas { list-style: none; margin: 0; padding: 0; }
.lista-citas li { min-width: 0; display: flex; align-items: center; gap: .75rem; padding: .55rem 0; }
.lista-citas li + li { border-top: 1px solid var(--borde); }
.hora { flex: none; width: 4.6rem; font-size: .88rem; font-weight: 700; font-variant-numeric: tabular-nums; }
.datos { min-width: 0; display: grid; line-height: 1.3; }
.datos small, .paciente { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.paciente { font-size: .92rem; font-weight: 600; }
.paciente { color: var(--tinta); text-decoration: none; }
.paciente:hover { color: var(--marca); text-decoration: underline; }
.datos small { font-size: .8rem; color: var(--tinta-suave); }
.lista-citas .enlace-flecha { margin-left: auto; flex: none; font-size: .82rem; }

/* La que ya empezó y la próxima se destacan con la barra de marca a la
   izquierda; la que está en curso, además, con fondo. */
.siguientes li.en-curso, .siguientes li.proxima {
  margin: 0 -.6rem; padding-inline: .6rem; border-radius: var(--radio);
  box-shadow: inset 3px 0 0 var(--marca);
}
.siguientes li.en-curso { background: var(--marca-tenue); }
.siguientes li.en-curso + li, .siguientes li.proxima + li { border-top-color: transparent; }

.mas { display: inline-block; margin-top: .4rem; font-size: .85rem; color: var(--tinta-suave); }
.mas:hover { color: var(--marca); }

.siguientes + .recuadro, .mas + .recuadro { margin-top: 1rem; }
.recuadro .lista-citas li { padding: .4rem 0; }
.recuadro .lista-citas li + li { border-top-color: color-mix(in srgb, var(--aviso) 18%, transparent); }
.recuadro .enlace-flecha { color: var(--aviso); }
</style>
