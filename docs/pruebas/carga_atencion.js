// Práctica 9 — tiempos del registro de una atención (POST /api/v1/atenciones/) con 5 usuarios.
//
// Solo reporta tiempos: no tiene umbral propio en los requisitos. Cada usuario
// virtual inicia sesión como la podóloga y registra atenciones sobre citas ya
// empezadas que prepara preparar_carga.py, con el monto del servicio y su
// insumo habitual: lo mismo que envía P11 al confirmar.
//
//   python docs/pruebas/preparar_carga.py 100 citas_carga.json
//   k6 run -e CITAS=citas_carga.json docs/pruebas/carga_atencion.js
import http from "k6/http";
import exec from "k6/execution";
import { check } from "k6";

const BASE = __ENV.BASE || "http://127.0.0.1:8000/api/v1";
const DATOS = JSON.parse(open(__ENV.CITAS));

export const options = {
  // La sesión se abre una vez por usuario: k6 no debe vaciar las cookies.
  noCookiesReset: true,
  scenarios: {
    registro: {
      executor: "shared-iterations",
      vus: 5,
      iterations: DATOS.citas.length,
      maxDuration: "5m",
    },
  },
  summaryTrendStats: ["min", "med", "avg", "p(90)", "p(95)", "p(99)", "max"],
  // Sin umbral de aceptación: el sub-métrico solo existe para que el resumen
  // muestre aparte los tiempos del registro.
  thresholds: {
    "http_req_duration{tipo:atencion}": ["max>=0"],
    "http_req_failed{tipo:atencion}": ["rate>=0"],
  },
};

function csrf() {
  return (http.cookieJar().cookiesForURL(BASE + "/").csrftoken || [""])[0];
}

let conSesion = false;

export default function () {
  if (!conSesion) {
    http.get(`${BASE}/sesion/actual/`);
    const r = http.post(`${BASE}/sesion/ingresar/`,
      JSON.stringify({ correo: "podologa@piessanos.pe", contrasena: "Podocenter2026" }),
      { headers: { "Content-Type": "application/json", "X-CSRFToken": csrf() } });
    check(r, { "inicio de sesión 200": (x) => x.status === 200 });
    conSesion = true;
  }
  const cita = DATOS.citas[exec.scenario.iterationInTest];
  const r = http.post(`${BASE}/atenciones/`, JSON.stringify({
    cita, monto_cobrado: DATOS.monto,
    observaciones_clinicas: "Atención registrada por la prueba de carga (Práctica 9).",
    insumos: DATOS.insumos,
  }), {
    headers: { "Content-Type": "application/json", "X-CSRFToken": csrf(),
      "X-Sede": String(DATOS.sede) },
    tags: { tipo: "atencion" },
  });
  check(r, { "atención 201": (x) => x.status === 201 });
}
