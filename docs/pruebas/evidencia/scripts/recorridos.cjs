// Práctica 9 — recorridos de sistema con Playwright.
//
// Un proyecto por corrida: chromium (escritorio), webkit (escritorio) o movil
// (Chromium a 390 × 844 px, táctil). Cada paso se hace con clics y teclado
// sobre la interfaz, deja una captura en docs/pruebas/capturas/<proyecto>/ y
// una línea con su resultado. Entre secciones se navega por URL, porque el
// menú cambia entre escritorio y móvil y no es lo que se prueba.
//
// Antes de cada proyecto hay que correr cargar_demo: el registro de la
// atención consume la cita en curso de la demostración.
//
//   NODE_PATH=<node_modules con playwright> node docs/pruebas/recorridos.cjs chromium
const path = require("path");
const fs = require("fs");
const { chromium, webkit } = require("playwright");

const BASE = process.env.BASE || "http://localhost:5173";
const CORREO = "podologa@piessanos.pe";
const CLAVE = "Podocenter2026"; // credencial pública de la demostración

const PROYECTOS = {
  chromium: { motor: chromium, contexto: { viewport: { width: 1366, height: 900 } } },
  webkit: { motor: webkit, contexto: { viewport: { width: 1366, height: 900 } } },
  movil: { motor: chromium,
    contexto: { viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true,
      deviceScaleFactor: 3 } },
};

const proyecto = process.argv[2];
if (!PROYECTOS[proyecto]) throw new Error(`Proyecto desconocido: ${proyecto}`);
// Copia para la evidencia: única diferencia con docs/pruebas/recorridos.cjs, la carpeta
// de las capturas, para no sobrescribir las del 18/11.
const CAPTURAS = path.join(__dirname, "..", "img", "E12-navegador", proyecto);
fs.mkdirSync(CAPTURAS, { recursive: true });

const resultados = [];
let numero = 0;

function fechaLocal(desfaseDias) {
  const d = new Date();
  d.setDate(d.getDate() + desfaseDias);
  if (d.getDay() === 0) d.setDate(d.getDate() + 1); // la sede cierra los domingos
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

async function paso(pagina, nombre, accion) {
  numero += 1;
  const archivo = `${String(numero).padStart(2, "0")}-${nombre.replace(/[^a-z0-9]+/gi, "-").toLowerCase()}.png`;
  const inicio = Date.now();
  try {
    const detalle = (await accion()) || "";
    await pagina.screenshot({ path: path.join(CAPTURAS, archivo), fullPage: true });
    resultados.push({ paso: nombre, resultado: "OK", detalle, ms: Date.now() - inicio, archivo });
  } catch (error) {
    await pagina.screenshot({ path: path.join(CAPTURAS, archivo), fullPage: true }).catch(() => {});
    resultados.push({ paso: nombre, resultado: "FALLA", detalle: error.message.split("\n")[0],
      ms: Date.now() - inicio, archivo });
  }
  const r = resultados[resultados.length - 1];
  console.log(`[${proyecto}] ${r.resultado.padEnd(5)} ${r.paso} (${r.ms} ms) — ${r.detalle} — img/E12-navegador/${proyecto}/${r.archivo}`);
}

(async () => {
  const navegador = await PROYECTOS[proyecto].motor.launch();
  const contexto = await navegador.newContext({ ...PROYECTOS[proyecto].contexto, locale: "es-PE",
    timezoneId: "America/Lima" });
  const pagina = await contexto.newPage();
  pagina.setDefaultTimeout(15000);
  const erroresDeConsola = [];
  pagina.on("console", (m) => { if (m.type() === "error") erroresDeConsola.push(m.text()); });
  pagina.on("pageerror", (e) => erroresDeConsola.push(String(e)));
  console.log(`[${proyecto}] ${PROYECTOS[proyecto].motor.name()} ${navegador.version()} · ` +
    `${JSON.stringify(PROYECTOS[proyecto].contexto.viewport)} · ${new Date().toISOString()}`);

  let sede = null;
  const api = async (ruta) => {
    const r = await pagina.request.get(`${BASE}/api/v1${ruta}`,
      { headers: sede ? { "X-Sede": String(sede) } : {} });
    return r.json();
  };

  // 1. Ingreso (P01) y elección de sede (P03)
  await paso(pagina, "ingreso", async () => {
    await pagina.goto(`${BASE}/ingresar`);
    await pagina.locator("#correo").fill(CORREO);
    await pagina.locator("#contrasena").fill(CLAVE);
    await pagina.getByRole("button", { name: "Ingresar", exact: true }).click();
    await pagina.waitForURL(/elegir-sede/);
    await pagina.getByRole("button", { name: /Sede Cercado/ }).click();
    await pagina.waitForURL(/panel/);
    sede = (await api("/sesion/sedes/")).sedes.find((s) => s.nombre === "Sede Cercado").id;
    return `panel del día abierto con la Sede Cercado (id ${sede})`;
  });

  // 2. Nueva cita (P06)
  const fechaCita = fechaLocal(6);
  await paso(pagina, "nueva cita", async () => {
    await pagina.goto(`${BASE}/agenda`);
    await pagina.getByRole("button", { name: "+ Nueva cita" }).click();
    await pagina.locator("#cita-paciente").fill("Quispe");
    await pagina.getByRole("button", { name: /Quispe Mamani, María Elena/ }).click();
    await pagina.locator("#cita-fecha").fill(fechaCita);
    await pagina.locator("#cita-hora").fill("12:00");
    const servicio = pagina.locator("#cita-servicio");
    const valor = await servicio.locator("option", { hasText: "Quiropodia general" }).getAttribute("value");
    await servicio.selectOption(valor);
    const profesional = pagina.locator("#cita-profesional");
    const valorProf = await profesional.locator("option", { hasText: "Lucía" }).getAttribute("value");
    await profesional.selectOption(valorProf);
    await pagina.getByRole("button", { name: "Guardar cita" }).click();
    const aviso = pagina.locator("p.aviso-ok[role=status]");
    await aviso.waitFor();
    return `aviso: «${(await aviso.innerText()).trim()}» (${fechaCita} 12:00)`;
  });

  // 3. Cancelar cita (P07): la que se acaba de crear
  await paso(pagina, "cancelar cita", async () => {
    await pagina.goto(`${BASE}/agenda`);
    await pagina.locator("#fecha").fill(fechaCita);
    await pagina.getByRole("button", { name: "Lista", exact: true }).click();
    await pagina.getByRole("button", { name: /Cancelar la cita de .*Quispe/ }).first().click();
    await pagina.locator("input[name=motivo]").first().check();
    await pagina.getByRole("button", { name: "Confirmar cancelación" }).click();
    const aviso = pagina.locator("p.aviso-ok[role=status]");
    await aviso.waitFor();
    return `aviso: «${(await aviso.innerText()).trim()}»`;
  });

  // 4. Registrar atención (P11) desde la agenda, contando las interacciones (RNF02)
  let interacciones = 0;
  const contar = async (promesa) => { interacciones += 1; return promesa; };
  await paso(pagina, "registrar atencion", async () => {
    const hoy = fechaLocal(0);
    const agenda = await api(`/citas/agenda/?fecha=${hoy}`);
    const cita = agenda.citas.find((c) => c.estado === "PROGRAMADA" && !c.tiene_atencion
      && new Date(c.inicio) <= new Date());
    if (!cita) throw new Error("no hay cita en curso: ¿se corrió cargar_demo?");
    await pagina.goto(`${BASE}/agenda`); // punto de partida: la agenda del día, vista por defecto
    // El bloque se busca por paciente, servicio y estado, no por la hora: la
    // cuadrícula la escribe en 24 horas y la lista en 12 («04:06 p. m.»).
    const bloque = pagina.locator(
      `button[aria-label*="${cita.paciente_nombre}, ${cita.servicio_nombre}, Programada"]`);
    // La agenda recuerda la última vista y el paso 3 dejó «Lista». Se vuelve a la
    // cuadrícula, la vista con que la agenda abre la primera vez; ese clic restaura
    // el punto de partida y no cuenta como interacción del registro.
    const cuadricula = pagina.getByRole("button", { name: "Cuadrícula del día" });
    if ((await cuadricula.getAttribute("aria-pressed")) !== "true") await cuadricula.click();
    await bloque.first().waitFor();
    // Desde aquí, cada acción del usuario suma una interacción.
    await contar(bloque.first().click());
    await contar(pagina.getByRole("region", { name: "Cita elegida" })
      .getByRole("link", { name: "Registrar atención" }).click());
    await pagina.waitForURL(/atencion/);
    const monto = await pagina.locator("#monto").inputValue();
    const insumos = await pagina.locator("table.tabla-insumos tbody tr").count();
    await contar(pagina.locator("#observaciones").fill("Recorrido de la Práctica 9."));
    await contar(pagina.getByRole("button", { name: "Confirmar atención" }).click());
    await pagina.waitForURL((u) => !/atencion/.test(u.pathname));
    const tras = (await api(`/citas/${cita.id}/`)).estado;
    return `${interacciones} interacciones; P11 precargó monto «${monto}» y ${insumos} insumo(s); ` +
      `la cita ${cita.id} quedó ${tras}`;
  });

  // 5. Ficha del paciente (P10)
  await paso(pagina, "ficha del paciente", async () => {
    await pagina.goto(`${BASE}/pacientes`);
    await pagina.locator("#buscar").fill("Quispe");
    await pagina.locator("form button[type=submit]").first().click();
    await pagina.getByRole("link", { name: /Quispe/ }).first().click();
    await pagina.waitForURL(/pacientes\/\d+/);
    // La ficha se pinta después de cambiar la URL: hasta entonces el h1 es el del listado.
    await pagina.waitForFunction(() => {
      const h1 = document.querySelector("h1");
      return h1 && h1.innerText.trim() !== "Pacientes";
    });
    const titulo = (await pagina.locator("h1").innerText()).trim();
    await pagina.getByText("Historial de atenciones").waitFor();
    await pagina.waitForLoadState("networkidle");
    const historial = await pagina.locator("table caption").count()
      ? (await pagina.locator("table caption").first().innerText()).trim()
      : "historial vacío: «" + (await pagina.getByText(/todavía no tiene atenciones/).innerText()).trim() + "»";
    return `«${titulo}» · ${historial}`;
  });

  // 6. Registrar movimiento de inventario (P13)
  await paso(pagina, "registrar movimiento", async () => {
    await pagina.goto(`${BASE}/inventario`);
    await pagina.getByRole("button", { name: "Registrar movimiento de Gasa estéril" }).click();
    await pagina.locator("#mov-tipo").selectOption("ENTRADA");
    await pagina.locator("#mov-cantidad").fill("5");
    await pagina.locator("#mov-motivo").fill("Compra a proveedor (recorrido P9)");
    await pagina.getByRole("dialog").getByRole("button", { name: "Registrar", exact: true }).click();
    const aviso = pagina.locator("p.aviso-ok[role=status]");
    await aviso.waitFor();
    return `aviso: «${(await aviso.innerText()).trim()}»`;
  });

  // 7. Disponibilidad entre sedes (P14)
  await paso(pagina, "disponibilidad entre sedes", async () => {
    await pagina.getByRole("button", { name: "Ver disponibilidad de Crema urea 10 %" }).click();
    const filas = pagina.locator("table.disponibilidad tbody tr");
    await filas.first().waitFor();
    const texto = (await filas.allInnerTexts()).map((t) => t.replace(/\s+/g, " ").trim());
    return `${await filas.count()} sede(s): ${texto.join(" | ")}`;
  });

  // 8. Registro diario (P16): hoy, con la atención del paso 4, y un día sin atenciones
  await paso(pagina, "registro diario con atenciones", async () => {
    await pagina.goto(`${BASE}/registro-diario`);
    const filas = pagina.locator("table.registro-diario tbody tr");
    await filas.first().waitFor();
    const total = (await pagina.locator("td.total").innerText()).trim();
    return `${await filas.count()} atención(es); total ${total}`;
  });
  await paso(pagina, "registro diario sin atenciones", async () => {
    await pagina.locator("#fecha-registro").fill("2026-01-04");
    await pagina.waitForTimeout(1500);
    const cuerpo = (await pagina.locator("main").innerText()).replace(/\s+/g, " ");
    const total = await pagina.locator("td.total").count()
      ? (await pagina.locator("td.total").innerText()).trim() : "(sin fila de total)";
    return `total mostrado: ${total} · texto: «${cuerpo.slice(0, 160)}…»`;
  });

  // 9. Desborde horizontal: la página no debe ser más ancha que la ventana.
  await paso(pagina, "ancho de las pantallas", async () => {
    const medidas = [];
    for (const ruta of ["/panel", "/agenda", "/pacientes", "/inventario", "/registro-diario"]) {
      await pagina.goto(`${BASE}${ruta}`);
      await pagina.waitForLoadState("networkidle");
      // Contra el ancho configurado y no contra innerWidth: en un móvil emulado,
      // la ventana de diseño crece con el contenido que desborda.
      const ventana = PROYECTOS[proyecto].contexto.viewport.width;
      const ancho = await pagina.evaluate(() => document.documentElement.scrollWidth);
      medidas.push(`${ruta} ${ancho}/${ventana} px${ancho > ventana ? " DESBORDA" : ""}`);
    }
    const desbordan = medidas.filter((m) => m.includes("DESBORDA"));
    if (desbordan.length) throw new Error(`desbordan: ${desbordan.join("; ")} · todas: ${medidas.join("; ")}`);
    return medidas.join("; ");
  });

  console.log(`[${proyecto}] errores de consola: ${erroresDeConsola.length ? erroresDeConsola.join(" || ") : "ninguno"}`);
  console.log(`[${proyecto}] resumen: ${resultados.filter((r) => r.resultado === "OK").length} de ${resultados.length} pasos OK`);
  console.log(JSON.stringify({ proyecto, interacciones_rnf02: interacciones, resultados }));
  await navegador.close();
})();
