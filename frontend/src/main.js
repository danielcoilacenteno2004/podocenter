// Punto de entrada del cliente.
//
// La sesión se restaura ANTES de montar la aplicación: si no, al recargar
// una página interna el guardia del router no sabría todavía que hay sesión
// abierta y devolvería al usuario al formulario de ingreso.
import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import { router } from './router'
import { useSesion } from './stores/sesion'
import './estilos.css'

const app = createApp(App)
const pinia = createPinia()
app.use(pinia)

const sesion = useSesion(pinia)
sesion.restaurar().finally(() => {
  app.use(router)
  app.mount('#app')
})
