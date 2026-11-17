// Formatos de presentación compartidos (es-PE). Una sola definición evita que
// la misma hora o el mismo monto se escriban distinto en dos pantallas.

const SOLES = new Intl.NumberFormat('es-PE', { style: 'currency', currency: 'PEN' })

export const soles = (valor) => SOLES.format(Number(valor) || 0)

export const hora = (valor) =>
  new Date(valor).toLocaleTimeString('es-PE', { hour: '2-digit', minute: '2-digit' })

// AAAA-MM-DD en la hora local. `toISOString()` daría la fecha UTC, que en
// Perú ya es «mañana» desde las 19:00.
export const hoy = () => new Date().toLocaleDateString('en-CA')

// Se ancla al mediodía para que un cambio de horario no mueva el día.
export function moverDias (fecha, dias) {
  const dia = new Date(`${fecha}T12:00`)
  dia.setDate(dia.getDate() + dias)
  return dia.toLocaleDateString('en-CA')
}

export const diaLargo = (fecha) =>
  new Date(`${fecha}T12:00`).toLocaleDateString('es-PE', {
    weekday: 'long', day: 'numeric', month: 'long', year: 'numeric'
  })

// 330 → «5 h 30 min»; 45 → «45 min»; 120 → «2 h».
export function duracion (minutos) {
  const horas = Math.floor(minutos / 60)
  const resto = minutos % 60
  if (!horas) return `${resto} min`
  return resto ? `${horas} h ${resto} min` : `${horas} h`
}
