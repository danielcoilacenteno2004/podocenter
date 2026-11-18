<script setup>
// Cabecera del panel del día: saludo, día, navegación y la cifra principal
// de cada segmento. Usa el mismo fondo de marca que el ingreso (P01), para
// que la primera pantalla tras entrar continúe el mismo lenguaje visual.
// El detalle de cada cifra está en su tarjeta, debajo; aquí no se repite.
// Cada cifra se compara con el promedio de los mismos días de la semana
// anteriores (lo calcula panel.py): sin referencia, un número no dice si el
// día va bien o mal.
import { computed } from 'vue'
import { useSesion } from '../../stores/sesion'
import { diaDeLaSemana, diaLargo, hoy, soles } from '../../formato'
import { usarCifraAnimada } from '../../composables/usarCifraAnimada'
import NavegadorDia from '../NavegadorDia.vue'

const fecha = defineModel('fecha', { type: String, required: true })
const props = defineProps({
  // null mientras llega la primera respuesta: las cifras se ven en esqueleto.
  panel: { type: Object, default: null }
})

const sesion = useSesion()

const saludo = computed(() => {
  const h = new Date().getHours()
  const parte = h < 12 ? 'Buenos días' : h < 19 ? 'Buenas tardes' : 'Buenas noches'
  const nombre = sesion.usuario?.nombre_completo?.split(' ')[0]
  return nombre ? `${parte}, ${nombre}` : parte
})

const sede = computed(() => sesion.sedeActiva?.nombre ?? props.panel?.sede?.nombre)

// En un día que ya pasó importa lo cobrado; en el de hoy y los que vienen,
// lo esperado. Cada uno se compara con su mismo promedio.
const pasado = computed(() => fecha.value < hoy())
const claveIngreso = computed(() => (pasado.value ? 'confirmado' : 'esperado'))

const total = usarCifraAnimada(() => props.panel?.citas.total)
const ingreso = usarCifraAnimada(() => props.panel?.ingresos[claveIngreso.value])
const ocupacion = usarCifraAnimada(() => props.panel?.ocupacion.porcentaje)

const numero = new Intl.NumberFormat('es-PE', { maximumFractionDigits: 1 })
const puntos = (valor) => `${numero.format(valor)} pts`

// «▲ 1,5 más que el promedio»; null si no hay con qué comparar.
function comparar (actual, referencia, formato) {
  if (referencia === null || referencia === undefined) return null
  const diferencia = Number(actual) - Number(referencia)
  if (Math.abs(diferencia) < 0.05) return { flecha: '=', texto: 'igual que el promedio' }
  return {
    flecha: diferencia > 0 ? '▲' : '▼',
    texto: `${formato(Math.abs(diferencia))} ${diferencia > 0 ? 'más' : 'menos'} que el promedio`
  }
}

const cifras = computed(() => {
  if (!props.panel) return null
  const { citas, ingresos, ocupacion: medida } = props.panel
  const clave = claveIngreso.value
  return [
    {
      clave: 'citas',
      etiqueta: 'Citas',
      valor: numero.format(Math.round(total.value)),
      detalle: `${citas.por_atender} por atender` +
        (citas.sin_registrar.length ? ` · ${citas.sin_registrar.length} sin registrar` : ''),
      comparacion: comparar(citas.total, citas.referencia.total, numero.format)
    },
    {
      clave: 'ingresos',
      etiqueta: pasado.value ? 'Ingreso cobrado' : 'Ingreso esperado',
      valor: soles(ingreso.value),
      detalle: pasado.value ? `de ${soles(ingresos.esperado)} esperados` : `${soles(ingresos.confirmado)} cobrados`,
      comparacion: comparar(ingresos[clave], ingresos.referencia[clave], soles)
    },
    medida.disponible
      ? {
          clave: 'ocupacion',
          etiqueta: 'Ocupación',
          valor: `${ocupacion.value.toFixed(1)} %`,
          detalle: 'de la capacidad vendida',
          comparacion: comparar(medida.porcentaje, medida.referencia.porcentaje, puntos)
        }
      : { clave: 'ocupacion', etiqueta: 'Ocupación', valor: '—', detalle: medida.detalle, comparacion: null }
  ]
})

// Una sola nota dice contra qué se compara, en lugar de repetirlo tres veces.
const notaComparacion = computed(() => {
  const dias = props.panel?.citas.referencia.dias
  if (dias === undefined) return ''
  const nombre = diaDeLaSemana(fecha.value)
  const plural = nombre.endsWith('s') ? nombre : `${nombre}s`   // lunes, sábados
  if (!dias) return `Sin ${plural} anteriores con la sede abierta para comparar.`
  return dias === 1
    ? `Comparado con el ${nombre} anterior.`
    : `Comparado con el promedio de los ${dias} ${plural} anteriores.`
})
</script>

<template>
  <header class="resumen fondo-marca">
    <div class="resumen-cabecera">
      <div>
        <p class="saludo">{{ saludo }}</p>
        <h1>Panel del día</h1>
        <p class="dia">
          {{ diaLargo(fecha) }}<template v-if="sede"> · {{ sede }}</template>
        </p>
      </div>
      <NavegadorDia v-model="fecha" tono="oscuro" etiqueta="Día del panel" />
    </div>

    <dl class="cifras">
      <template v-if="cifras">
        <div v-for="cifra in cifras" :key="cifra.clave" class="cifra">
          <dt>{{ cifra.etiqueta }}</dt>
          <dd class="valor">{{ cifra.valor }}</dd>
          <dd class="detalle">{{ cifra.detalle }}</dd>
          <dd v-if="cifra.comparacion" class="comparacion">
            <span aria-hidden="true">{{ cifra.comparacion.flecha }}</span> {{ cifra.comparacion.texto }}
          </dd>
        </div>
      </template>
      <template v-else>
        <div v-for="etiqueta in ['Citas', 'Ingresos', 'Ocupación']" :key="etiqueta" class="cifra">
          <dt>{{ etiqueta }}</dt>
          <dd class="esqueleto" />
        </div>
      </template>
    </dl>
    <p v-if="notaComparacion" class="nota-comparacion">{{ notaComparacion }}</p>
  </header>
</template>

<style scoped>
.resumen {
  --tenue: color-mix(in srgb, var(--blanco) 72%, transparent);
  --linea: color-mix(in srgb, var(--blanco) 16%, transparent);
  margin-bottom: 1.5rem; padding: clamp(1.5rem, 4vw, 2.25rem);
  border-radius: var(--radio-tarjeta); box-shadow: var(--sombra-alta);
  animation: subir .35s var(--transicion) both;
}
/* En una franja ancha la hoja del logo se queda en una esquina. */
.resumen::after { width: 34%; right: -4%; bottom: -45%; }

.resumen-cabecera { display: flex; justify-content: space-between; align-items: flex-end; flex-wrap: wrap; gap: 1.25rem 2rem; }
.saludo { margin: 0 0 .2rem; color: var(--tenue); font-weight: 600; font-size: .92rem; }
h1 { margin: 0; color: var(--blanco); font-size: clamp(1.6rem, 3vw, 2rem); letter-spacing: -.02em; }
.dia { margin: .3rem 0 0; color: var(--tenue); }
.dia::first-letter { text-transform: uppercase; }

.cifras {
  display: grid; grid-template-columns: repeat(3, minmax(0, 1fr));
  margin: 1.75rem 0 0; padding-top: 1.5rem; border-top: 1px solid var(--linea);
}
.cifra { min-width: 0; padding-right: 1.5rem; }
.cifra + .cifra { padding-left: 1.5rem; border-left: 1px solid var(--linea); }
.cifra dt { font-size: .72rem; font-weight: 700; letter-spacing: .08em; text-transform: uppercase; color: var(--tenue); }
.cifra .valor {
  margin: .35rem 0 0; font-size: clamp(1.8rem, 3.6vw, 2.5rem); font-weight: 700; line-height: 1.1;
  letter-spacing: -.02em; font-variant-numeric: tabular-nums;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.cifra .detalle { margin: .25rem 0 0; font-size: .88rem; color: var(--tenue); }
.cifra .comparacion {
  display: inline-block; margin: .6rem 0 0; padding: .15rem .55rem; border-radius: 999px;
  font-size: .78rem; font-weight: 600; color: var(--blanco);
  background: color-mix(in srgb, var(--blanco) 12%, transparent);
}
.nota-comparacion { margin: 1.1rem 0 0; font-size: .78rem; color: var(--tenue); }
.cifra .esqueleto { width: 60%; height: 2.4rem; margin: .45rem 0 0; background: color-mix(in srgb, var(--blanco) 12%, transparent); }
/* El brillo del esqueleto está pensado para fondo claro; sobre la franja
   oscura se atenúa para que no destaque más que las cifras. */
.cifra .esqueleto::after { background: linear-gradient(90deg, transparent, color-mix(in srgb, var(--blanco) 14%, transparent), transparent); }

@media (max-width: 640px) {
  .cifras { grid-template-columns: minmax(0, 1fr); gap: 1rem; }
  .cifra { padding-right: 0; }
  .cifra + .cifra { padding: 1rem 0 0; border-left: 0; border-top: 1px solid var(--linea); }
}
</style>
