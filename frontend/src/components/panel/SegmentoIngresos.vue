<script setup>
// Segmento «Ingresos» del panel del día: cuánto de lo esperado ya está
// confirmado y de qué servicios sale.
import { computed } from 'vue'
import { soles } from '../../formato'
import IconoTrazo from '../IconoTrazo.vue'
import TarjetaSeccion from '../TarjetaSeccion.vue'

const props = defineProps({
  ingresos: { type: Object, required: true },
  fecha: { type: String, required: true }
})

const porcentajeConfirmado = computed(() => {
  const esperado = Number(props.ingresos.esperado)
  return esperado ? Math.round(Number(props.ingresos.confirmado) * 100 / esperado) : 0
})

const montoMaximo = computed(() => Math.max(0, ...props.ingresos.por_servicio.map((fila) => Number(fila.monto))))
const proporcion = (monto) => montoMaximo.value ? Number(monto) * 100 / montoMaximo.value : 0
</script>

<template>
  <TarjetaSeccion icono="billete" :titulo="ingresos.titulo" descripcion="Esperado frente a lo cobrado">
    <div class="confirmado">
      <span>Cobrado</span>
      <span><strong>{{ soles(ingresos.confirmado) }}</strong> de {{ soles(ingresos.esperado) }} · {{ porcentajeConfirmado }} %</span>
    </div>
    <div class="progreso" role="img" :aria-label="`${porcentajeConfirmado} por ciento del ingreso esperado ya cobrado`">
      <span :style="{ width: `${porcentajeConfirmado}%` }" />
    </div>

    <dl class="datos-breves">
      <div><dt>Ticket promedio</dt><dd>{{ soles(ingresos.ticket_promedio) }}</dd></div>
      <div :class="{ perdido: Number(ingresos.perdido) > 0 }">
        <dt>No concretado</dt><dd>{{ soles(ingresos.perdido) }}</dd>
      </div>
    </dl>

    <template v-if="ingresos.por_servicio.length">
      <h3 class="titulo-grupo">Por servicio</h3>
      <!-- Al cambiar de día, los servicios que siguen se reordenan con un
           desplazamiento y los que entran o salen se funden. -->
      <TransitionGroup tag="ul" name="lista" class="servicios">
        <li v-for="fila in ingresos.por_servicio" :key="fila.servicio_id">
          <router-link :to="{ name: 'agenda', query: { fecha, servicio: fila.servicio_id } }">
            {{ fila.servicio }}
          </router-link>
          <span class="servicio-citas">{{ fila.citas }} cita(s)</span>
          <span class="servicio-monto">{{ soles(fila.monto) }}</span>
          <span class="servicio-barra" aria-hidden="true">
            <span :style="{ width: `${proporcion(fila.monto)}%` }" />
          </span>
        </li>
      </TransitionGroup>
    </template>

    <template #pie>
      <p class="nota">
        <IconoTrazo nombre="info" :tamano="15" />
        <span>{{ ingresos.nota }} Cada servicio abre la agenda del día filtrada por él.</span>
      </p>
      <p v-if="ingresos.sin_monto">
        {{ ingresos.sin_monto }} atención(es) se registraron antes de que existiera el monto
        cobrado y no suman, igual que en el registro diario.
      </p>
    </template>
  </TarjetaSeccion>
</template>

<style scoped>
.confirmado { display: flex; justify-content: space-between; gap: .5rem 1rem; flex-wrap: wrap; margin-bottom: .5rem; font-size: .9rem; color: var(--tinta-suave); }
.confirmado strong { color: var(--tinta); font-variant-numeric: tabular-nums; }
.progreso { margin-bottom: 1.25rem; }
.perdido dd { color: var(--alerta); }

.titulo-grupo { margin-top: 1.4rem; }
.servicios { position: relative; list-style: none; margin: 0; padding: 0; display: grid; gap: .7rem; }
.servicios li { display: grid; grid-template-columns: minmax(0, 1fr) auto auto; gap: .25rem .75rem; align-items: baseline; font-size: .92rem; }
.servicios a { font-weight: 600; color: var(--tinta); text-decoration: none; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.servicios a:hover { color: var(--marca); text-decoration: underline; }
.servicio-citas { font-size: .8rem; color: var(--tinta-suave); }
.servicio-monto { font-weight: 700; font-variant-numeric: tabular-nums; text-align: right; }
.servicio-barra { grid-column: 1 / -1; height: 3px; border-radius: 999px; background: var(--fondo); overflow: hidden; }
.servicio-barra span { display: block; height: 100%; background: var(--oficial-claro); transition: width .5s var(--transicion); }

.lista-move, .lista-enter-active, .lista-leave-active { transition: transform .35s var(--transicion), opacity .35s var(--transicion); }
.lista-enter-from, .lista-leave-to { opacity: 0; transform: translateY(6px); }
/* El que sale deja de ocupar sitio para que los demás se muevan suaves. */
.lista-leave-active { position: absolute; width: 100%; }

.nota { display: flex; gap: .45rem; }
.nota svg { flex: none; margin-top: .15rem; }
</style>
