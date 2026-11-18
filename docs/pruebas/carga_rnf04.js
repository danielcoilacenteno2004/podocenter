// Práctica 9 — prueba de carga del RNF04: disponibilidad entre sedes (P14) en menos de 2 s.
//
// Cada usuario virtual inicia sesión una vez como la podóloga de la demostración
// y consulta, una y otra vez, la disponibilidad de un producto en todas las sedes
// (GET /api/v1/inventario/disponibilidad/), con un segundo de pausa entre
// consultas, como alguien que mira la pantalla.
//
// Escalones de 1, 5, 10 y 20 usuarios, 1 minuto cada uno, uno tras otro.
// Umbral: p(95) < 2000 ms y menos del 1 % de errores, en cada escalón.
//
//   k6 run --summary-mode=full docs/pruebas/carga_rnf04.js
import http from "k6/http";
import { check, sleep } from "k6";

const BASE = __ENV.BASE || "http://127.0.0.1:8000/api/v1";
const CORREO = "podologa@piessanos.pe";
const CLAVE = "Podocenter2026"; // credencial pública de la demostración
const PRODUCTO = "INS-004";

const ESCALONES = [1, 5, 10, 20];
const scenarios = {};
const thresholds = {};
ESCALONES.forEach((vus, i) => {
  const nombre = `vu${String(vus).padStart(2, "0")}`;
  scenarios[nombre] = {
    executor: "constant-vus",
    vus,
    duration: "1m",
    startTime: `${i * 65}s`, // 5 s de margen para que termine el escalón anterior
    gracefulStop: "5s",
  };
  thresholds[`http_req_duration{scenario:${nombre},tipo:disponibilidad}`] = ["p(95)<2000"];
  thresholds[`http_req_failed{scenario:${nombre},tipo:disponibilidad}`] = ["rate<0.01"];
});
thresholds["http_req_duration{tipo:disponibilidad}"] = ["p(95)<2000"];
thresholds["http_req_failed{tipo:disponibilidad}"] = ["rate<0.01"];

export const options = {
  // k6 vacía las cookies al empezar cada iteración; sin esto, solo la primera
  // consulta de cada usuario llevaría la sesión (corrida descartada del 18/11).
  noCookiesReset: true,
  scenarios,
  thresholds,
  summaryTrendStats: ["min", "med", "avg", "p(90)", "p(95)", "p(99)", "max"],
};

function csrf() {
  const galletas = http.cookieJar().cookiesForURL(BASE + "/");
  return (galletas.csrftoken || [""])[0];
}

export function iniciarSesion() {
  http.get(`${BASE}/sesion/actual/`, { tags: { tipo: "sesion" } });
  const r = http.post(
    `${BASE}/sesion/ingresar/`,
    JSON.stringify({ correo: CORREO, contrasena: CLAVE }),
    { headers: { "Content-Type": "application/json", "X-CSRFToken": csrf() },
      tags: { tipo: "sesion" } },
  );
  check(r, { "inicio de sesión 200": (x) => x.status === 200 });
}

export function setup() {
  iniciarSesion();
  const sedes = http.get(`${BASE}/sesion/sedes/`).json("sedes");
  const sede = sedes.find((s) => s.nombre === "Sede Cercado").id;
  const productos = http.get(`${BASE}/inventario/productos/?buscar=${PRODUCTO}`,
    { headers: { "X-Sede": String(sede) } }).json("productos");
  return { sede, producto: productos[0].id };
}

let conSesion = false; // ámbito del módulo: uno por usuario virtual

export default function (datos) {
  if (!conSesion) {
    iniciarSesion();
    conSesion = true;
  }
  const r = http.get(`${BASE}/inventario/disponibilidad/?producto=${datos.producto}`, {
    headers: { "X-Sede": String(datos.sede) },
    tags: { tipo: "disponibilidad" },
  });
  check(r, {
    "disponibilidad 200": (x) => x.status === 200,
    "dos sedes en la respuesta": (x) => x.status === 200 && x.json("sedes").length === 2,
  });
  sleep(1);
}
