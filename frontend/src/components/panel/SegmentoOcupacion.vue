<script setup>
// Segmento «Ocupación» del panel del día: cuánto de la capacidad de la sede
// ya está agendado, y cuánto tiene cada profesional. La capacidad es la de
// cada profesional por el horario de la sede (lo calcula panel.py); el
// desglose dice dónde quedan los huecos, y los siete días siguientes, lo
// que todavía se puede llenar.
import { computed } from 'vue'
import { diaDeLaSemana, duracion } from '../../formato'
import IconoTrazo from '../IconoTrazo.vue'
import TarjetaSeccion from '../TarjetaSeccion.vue'

const props = defineProps({
  ocupacion: { type: Object, required: true }
})

// El servidor escribe el horario como «08:00 a 19:00» (panel.py); se separa
// para rotular los extremos de la barra.
const extremos = computed(() => props.ocupacion.horario?.split(' a ') ?? [])
const ancho = (porcentaje) => `${Math.min(porcentaje ?? 0, 100)}%`

// Cada día siguiente es un enlace al panel de ese día.
const proximos = computed(() => (props.ocupacion.proximos ?? []).map((dia) => ({
  ...dia,
  semana: diaDeLaSemana(dia.fecha, 'short').replace('.', ''),
  numero: Number(dia.fecha.slice(8)),
  etiqueta: dia.abierta
    ? `${diaDeLaSemana(dia.fecha)} ${Number(dia.fecha.slice(8))}: ${dia.porcentaje} % ocupado`
    : `${diaDeLaSemana(dia.fecha)} ${Number(dia.fecha.slice(8))}: la sede no atiende`
})))

const descripcion = computed(() => {
  const n = props.ocupacion.profesionales?.length
  return n ? `${n} profesional(es) · de ${props.ocupacion.horario}` : 'Capacidad de la sede'
})
</script>

<template>
  <TarjetaSeccion icono="reloj" :titulo="ocupacion.titulo" :descripcion="descripcion">
    <div v-if="ocupacion.disponible" class="ocupacion">
      <div>
        <div class="progreso progreso-jornada" role="img"
             :aria-label="`${ocupacion.porcentaje} por ciento de la capacidad de la sede ocupada`">
          <span :style="{ width: ancho(ocupacion.porcentaje) }" />
        </div>
        <div v-if="extremos.length === 2" class="extremos" aria-hidden="true">
          <span>{{ extremos[0] }}</span><span>{{ extremos[1] }}</span>
        </div>

        <dl class="datos-breves">
          <div><dt><span class="muestra agendado" aria-hidden="true" />Agendado</dt><dd>{{ duracion(ocupacion.minutos_agendados) }}</dd></div>
          <div><dt><span class="muestra libre" aria-hidden="true" />Libre</dt><dd>{{ duracion(ocupacion.libres) }}</dd></div>
          <div><dt>Capacidad</dt><dd>{{ duracion(ocupacion.minutos_disponibles) }}</dd></div>
        </dl>
      </div>

      <div>
        <h3 class="titulo-grupo">Por profesional</h3>
        <ul class="profesionales">
          <li v-for="p in ocupacion.profesionales" :key="p.id">
            <span class="nombre">{{ p.nombre }}</span>
            <span class="valor">{{ duracion(p.minutos_agendados) }} · {{ p.porcentaje }} %</span>
            <div class="progreso" role="img" :aria-label="`${p.nombre}: ${p.porcentaje} por ciento de su jornada ocupada`">
              <span :style="{ width: ancho(p.porcentaje) }" />
            </div>
          </li>
        </ul>
      </div>
    </div>
    <p v-else class="recuadro recuadro-con-icono">
      <IconoTrazo nombre="cerrado" />
      {{ ocupacion.detalle }}
    </p>

    <template v-if="proximos.length">
      <h3 class="titulo-grupo titulo-proximos">Próximos 7 días</h3>
      <ol class="proximos">
        <li v-for="dia in proximos" :key="dia.fecha">
          <router-link :to="{ name: 'panel', query: { fecha: dia.fecha } }" :aria-label="dia.etiqueta" :class="{ cerrada: !dia.abierta }">
            <span class="proximos-valor" aria-hidden="true">{{ dia.abierta ? `${Math.round(dia.porcentaje)} %` : '—' }}</span>
            <span class="proximos-columna" aria-hidden="true">
              <span v-if="dia.abierta" :style="{ height: ancho(dia.porcentaje) }" />
            </span>
            <span class="proximos-dia" aria-hidden="true">{{ dia.semana }} {{ dia.numero }}</span>
          </router-link>
        </li>
      </ol>
    </template>

    <!-- El sistema no guarda horarios por profesional: decirlo evita leer la
         capacidad como si fuera exacta. -->
    <template v-if="ocupacion.disponible || proximos.length" #pie>
      <p>Se supone que cada profesional cubre el horario completo de la sede.</p>
    </template>
  </TarjetaSeccion>
</template>

<style scoped>
.ocupacion { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); gap: 1.25rem 2.5rem; }
@media (max-width: 780px) { .ocupacion { grid-template-columns: minmax(0, 1fr); } }

.progreso-jornada { height: .8rem; }
.extremos { display: flex; justify-content: space-between; margin: .4rem 0 1.1rem; font-size: .78rem; color: var(--tinta-suave); font-variant-numeric: tabular-nums; }
.muestra { width: .55rem; height: .55rem; border-radius: 50%; }
.muestra.agendado { background: var(--marca); }
.muestra.libre { background: var(--borde); }

.profesionales { list-style: none; margin: 0; padding: 0; display: grid; gap: .8rem; }
.profesionales li { display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: .3rem .75rem; align-items: baseline; font-size: .92rem; }
.nombre { font-weight: 600; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.valor { font-size: .82rem; color: var(--tinta-suave); font-variant-numeric: tabular-nums; }
.profesionales .progreso { grid-column: 1 / -1; height: .4rem; }
.profesionales .progreso > span { background: var(--oficial-medio); }

/* Barras de los días siguientes. Un día cerrado se rellena con rayas y se
   rotula «—»: no depende del color para leerse (RNF05). */
.titulo-proximos { margin-top: 1.6rem; }
.proximos { list-style: none; margin: 0; padding: 0; display: grid; grid-template-columns: repeat(7, minmax(0, 1fr)); gap: .5rem; }
.proximos a {
  display: grid; justify-items: center; gap: .3rem; padding: .4rem .2rem;
  border-radius: var(--radio); text-decoration: none; color: var(--tinta);
  transition: background-color var(--transicion);
}
.proximos a:hover { background: var(--fondo); }
.proximos-valor { font-size: .78rem; font-weight: 700; font-variant-numeric: tabular-nums; }
.proximos-columna {
  position: relative; width: 100%; max-width: 2.25rem; height: 4.5rem;
  border-radius: 6px; background: var(--fondo); overflow: hidden;
}
.proximos-columna span {
  position: absolute; inset: auto 0 0; min-height: 2px; background: var(--marca);
  transform-origin: bottom; animation: crecer-alto .6s var(--transicion) both;
}
.cerrada .proximos-columna {
  background: repeating-linear-gradient(135deg, var(--fondo) 0 4px, var(--borde) 4px 6px);
}
.cerrada .proximos-valor { color: var(--tinta-suave); }
.proximos-dia { font-size: .75rem; color: var(--tinta-suave); text-transform: capitalize; }
@keyframes crecer-alto { from { transform: scaleY(0); } }
</style>
