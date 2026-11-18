<script setup>
// P04 Panel del día (CU04). La observación de la Práctica N.° 7 pedía
// segmentar el panel en lugar de apilar indicadores sueltos: cada bloque
// responde a una decisión distinta de la dueña del centro (citas, ingresos y
// ocupación). La vista solo compone: la carga vive en usarPanelDelDia y cada
// segmento es un componente.
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { hoy } from '../formato'
import { usarPanelDelDia } from '../composables/usarPanelDelDia'
import ResumenDelDia from '../components/panel/ResumenDelDia.vue'
import SegmentoCitas from '../components/panel/SegmentoCitas.vue'
import SegmentoIngresos from '../components/panel/SegmentoIngresos.vue'
import SegmentoOcupacion from '../components/panel/SegmentoOcupacion.vue'

const ruta = useRoute()
const router = useRouter()

// El día vive en la dirección (?fecha=AAAA-MM-DD): atrás y adelante del
// navegador recorren los días vistos y el enlace se puede compartir. Hoy no
// se escribe, para que /panel siga siendo «el panel de hoy».
const fecha = computed({
  get: () => (typeof ruta.query.fecha === 'string' && ruta.query.fecha) || hoy(),
  set: (dia) => router.push({ query: { ...ruta.query, fecha: dia === hoy() ? undefined : dia } })
})

const { panel, error, cargando, actualizando, recargar } = usarPanelDelDia(fecha)
</script>

<template>
  <main>
    <ResumenDelDia v-model:fecha="fecha" :panel="panel" />

    <Transition name="aparecer">
      <div v-if="error" class="error-carga" role="alert">
        <span>{{ error }}</span>
        <button class="secundario boton-fila" type="button" @click="recargar">Reintentar</button>
      </div>
    </Transition>
    <p v-if="cargando" class="solo-lectores" role="status">Cargando el panel…</p>

    <!-- Primera carga: esqueleto con la forma de los tres segmentos. -->
    <div v-if="cargando" class="segmentos" aria-hidden="true">
      <div v-for="n in 3" :key="n" class="tarjeta">
        <span class="esqueleto esqueleto-titulo" />
        <span class="esqueleto esqueleto-barra" />
        <span class="esqueleto esqueleto-linea" />
        <span class="esqueleto esqueleto-linea corta" />
      </div>
    </div>

    <!-- Al cambiar a un día no visto se conservan las cifras anteriores,
         atenuadas, hasta que llegan las nuevas: la página no parpadea. -->
    <div v-else-if="panel" class="segmentos" :class="{ actualizando }" :aria-busy="actualizando">
      <SegmentoCitas :citas="panel.citas" :fecha="fecha" />
      <SegmentoIngresos :ingresos="panel.ingresos" :fecha="fecha" />
      <SegmentoOcupacion :ocupacion="panel.ocupacion" />
    </div>
  </main>
</template>

<style scoped>
.segmentos {
  display: grid;
  gap: 1.25rem;
  /* Citas e Ingresos comparten la primera fila; Ocupación ocupa el ancho
     completo debajo, porque su contenido es una barra y tres cifras. En
     celular los tres pasan a una sola columna. */
  grid-template-columns: repeat(2, minmax(0, 1fr));
  transition: opacity var(--transicion);
}
.segmentos > :nth-child(2) { animation-delay: 60ms; }
.segmentos > :nth-child(3) { grid-column: 1 / -1; animation-delay: 120ms; }
.segmentos.actualizando { opacity: .55; }
@media (max-width: 780px) {
  .segmentos { grid-template-columns: minmax(0, 1fr); }
}

.error-carga { display: flex; align-items: center; justify-content: space-between; gap: .75rem; flex-wrap: wrap; }

.esqueleto-titulo { width: 40%; height: 1.4rem; }
.esqueleto-barra { width: 100%; height: .6rem; margin-top: 1.5rem; }
.esqueleto-linea { width: 85%; height: 1rem; margin-top: .9rem; }
.esqueleto-linea.corta { width: 55%; }
</style>
