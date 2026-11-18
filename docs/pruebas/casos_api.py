"""Práctica 9 — casos pendientes (CP) y correcciones del 11/11 (DEF) contra la API real.

Habla por HTTP con el servidor en marcha, como lo haría el navegador: sesión
por cookie, CSRF y sede activa en la cabecera X-Sede. Escribe cada petición y
su respuesta, sin resumir, en la salida estándar; al final, una tabla con lo
esperado, lo obtenido y si coincide.

Requisitos: `cargar_demo` recién corrido (para que haya una cita en curso) y
el servidor en http://127.0.0.1:8000.

    python docs/pruebas/casos_api.py > docs/pruebas/06_casos.txt

Solo usa la biblioteca estándar. No corrige nada: si un caso no da lo
esperado, queda anotado como NO COINCIDE y se sigue con el siguiente.
"""
import http.cookiejar
import json
import sys
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta, timezone

sys.stdout.reconfigure(encoding="utf-8")

BASE = "http://127.0.0.1:8000/api/v1"
CLAVE = "Podocenter2026"  # credencial pública de la demostración  # nosec B105
LIMA = timezone(timedelta(hours=-5))
RESULTADOS = []


class Cliente:
    """Un navegador mínimo: guarda la cookie de sesión y manda el CSRF."""

    def __init__(self, nombre):
        self.nombre = nombre
        self.galletas = http.cookiejar.CookieJar()
        self.abridor = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self.galletas))
        self.sede = None

    def _csrf(self):
        return next((c.value for c in self.galletas if c.name == "csrftoken"), "")

    def pedir(self, metodo, ruta, cuerpo=None, mostrar=True):
        # S310: las URL salen siempre de BASE, una constante http:// local.
        if not self._csrf():
            self.abridor.open(urllib.request.Request(BASE + "/sesion/actual/"))  # noqa: S310
        datos = None if cuerpo is None else json.dumps(cuerpo).encode()
        peticion = urllib.request.Request(BASE + ruta, data=datos, method=metodo)  # noqa: S310
        peticion.add_header("Content-Type", "application/json")
        peticion.add_header("X-CSRFToken", self._csrf())
        if self.sede:
            peticion.add_header("X-Sede", str(self.sede))
        try:
            with self.abridor.open(peticion) as respuesta:
                estado, texto = respuesta.status, respuesta.read().decode()
        except urllib.error.HTTPError as error:
            estado, texto = error.code, error.read().decode()
        try:
            contenido = json.loads(texto) if texto else None
        except json.JSONDecodeError:
            contenido = texto
        if mostrar:
            print(f"\n[{self.nombre}] {metodo} /api/v1{ruta}"
                  + (f"  (X-Sede: {self.sede})" if self.sede else ""))
            if cuerpo is not None:
                print("  cuerpo enviado: " + json.dumps(cuerpo, ensure_ascii=False))
            print(f"  -> HTTP {estado}")
            print("  " + _recortar(texto))
        return estado, contenido

    def entrar(self, correo, clave=CLAVE):
        return self.pedir("POST", "/sesion/ingresar/", {"correo": correo, "contrasena": clave})


def _recortar(texto, limite=2500):
    if len(texto) <= limite:
        return texto
    return texto[:limite] + f" […recortado: {len(texto) - limite} caracteres más]"


def titulo(texto):
    print("\n" + "=" * 78 + f"\n{texto}\n" + "=" * 78)


def anotar(caso, esperado, obtenido, coincide):
    RESULTADOS.append((caso, esperado, obtenido, "COINCIDE" if coincide else "NO COINCIDE"))
    print(f"  >>> {caso}: {'COINCIDE' if coincide else 'NO COINCIDE'} — obtenido: {obtenido}")


def lista(contenido):
    return contenido["results"] if isinstance(contenido, dict) and "results" in contenido \
        else contenido


def codigo(contenido):
    return contenido.get("codigo") if isinstance(contenido, dict) else None


def principal():
    print(f"Ejecución: {datetime.now(LIMA).isoformat(timespec='seconds')}  Base: {BASE}")

    admin = Cliente("gerencia")
    admin.entrar("gerencia@piessanos.pe")
    _, sedes = admin.pedir("GET", "/sedes/", mostrar=False)
    sedes = {s["nombre"]: s for s in lista(sedes)}
    cercado, bustamante = sedes["Sede Cercado"]["id"], sedes["Sede Bustamante"]["id"]
    admin.sede = cercado

    # ------------------------------------------------------------------ CP-02
    titulo("CP-02 — Contraseña errónea y correo inexistente: misma respuesta 401")
    anonimo = Cliente("anónimo")
    e1, c1 = anonimo.entrar("gerencia@piessanos.pe", "ClaveEquivocada1")
    e2, c2 = anonimo.entrar("no.existe@piessanos.pe", "ClaveEquivocada1")
    anotar("CP-02", "401 idéntico en ambos casos",
           f"{e1} y {e2}; cuerpos {'idénticos' if c1 == c2 else 'distintos'}",
           e1 == e2 == 401 and c1 == c2)

    # ------------------------------------------------------------------ CP-03
    titulo("CP-03 — Cinco intentos fallidos seguidos: ¿bloqueo temporal?")
    atacante = Cliente("intentos")
    for intento in range(1, 6):
        print(f"\n  intento fallido {intento}")
        atacante.entrar("podologa@piessanos.pe", f"Equivocada{intento}")
    print("\n  sexto intento, con la contraseña correcta, inmediatamente después")
    e6, c6 = atacante.entrar("podologa@piessanos.pe")
    anotar("CP-03", "sexto intento rechazado por bloqueo temporal",
           f"HTTP {e6}" + (" (entró: no hay bloqueo)" if e6 == 200 else f" codigo={codigo(c6)}"),
           e6 != 200)

    # ------------------------------------------------------------------ CP-20
    titulo("CP-20 — PATCH /pacientes/{id}/ debe responder 405")
    _, pacientes = admin.pedir("GET", "/pacientes/", mostrar=False)
    paciente = lista(pacientes)[0]
    e, _ = admin.pedir("PATCH", f"/pacientes/{paciente['id']}/", {"telefono": "900000000"})
    anotar("CP-20", "405", f"HTTP {e}", e == 405)

    # ------------------------------------------------- CP-32 (atención con insumos)
    titulo("CP-32 — Atención con insumos: stock, monto y cita atendida; sin stock, nada")
    podologa = Cliente("podóloga")
    podologa.entrar("podologa@piessanos.pe")
    podologa.sede = cercado
    hoy = date.today().isoformat()
    _, agenda = podologa.pedir("GET", f"/citas/agenda/?fecha={hoy}", mostrar=False)
    ahora = datetime.now(LIMA)
    en_curso = [c for c in agenda["citas"] if c["estado"] == "PROGRAMADA"
                and datetime.fromisoformat(c["inicio"]) <= ahora and not c["tiene_atencion"]]
    if not en_curso:
        anotar("CP-32", "cita en curso disponible", "no hay cita en curso (¿cargar_demo?)", False)
        return
    cita = en_curso[0]
    print(f"\n  cita en curso elegida: {json.dumps(cita, ensure_ascii=False)}")
    _, servicio = admin.pedir("GET", f"/servicios/{cita['servicio']}/")
    habitual = servicio["insumos_habituales"][0]
    _, stock = podologa.pedir("GET", "/inventario/stock/")
    antes = next(f["cantidad"] for f in stock["stock"] if f["id"] == habitual["producto"])

    print("\n  (a) con stock insuficiente")
    e, c = podologa.pedir("POST", "/atenciones/", {
        "cita": cita["id"], "monto_cobrado": "65.00", "observaciones_clinicas": "Prueba CP-32a",
        "insumos": [{"producto": habitual["producto"], "cantidad": antes + 100}]})
    _, cita_tras = podologa.pedir("GET", f"/citas/{cita['id']}/")
    _, stock = podologa.pedir("GET", "/inventario/stock/", mostrar=False)
    tras_a = next(f["cantidad"] for f in stock["stock"] if f["id"] == habitual["producto"])
    _, atenciones = podologa.pedir("GET", f"/atenciones/?paciente={cita['paciente']}",
                                   mostrar=False)
    de_la_cita = [a for a in lista(atenciones) if a["cita"] == cita["id"]]
    print(f"  stock antes {antes}, después {tras_a}; atenciones de la cita: {len(de_la_cita)}")
    anotar("CP-32 sin stock", "422 stock-insuficiente, sin atención, stock igual, cita programada",
           f"HTTP {e} {codigo(c)}; atenciones={len(de_la_cita)}; stock {antes}->{tras_a}; "
           f"cita {cita_tras['estado']}",
           e == 422 and not de_la_cita and tras_a == antes and cita_tras["estado"] == "PROGRAMADA")

    print("\n  (b) con stock suficiente")
    e, atencion = podologa.pedir("POST", "/atenciones/", {
        "cita": cita["id"], "monto_cobrado": "65.00", "observaciones_clinicas": "Prueba CP-32b",
        "insumos": [{"producto": habitual["producto"], "cantidad": 1}]})
    _, cita_tras = podologa.pedir("GET", f"/citas/{cita['id']}/")
    _, stock = podologa.pedir("GET", "/inventario/stock/", mostrar=False)
    tras_b = next(f["cantidad"] for f in stock["stock"] if f["id"] == habitual["producto"])
    print(f"  stock antes {antes}, después {tras_b}")
    monto = atencion.get("monto_cobrado") if isinstance(atencion, dict) else None
    anotar("CP-32 con stock", "201, stock -1, monto 65.00, cita ATENDIDA",
           f"HTTP {e}; stock {antes}->{tras_b}; monto {monto}; cita {cita_tras['estado']}",
           e == 201 and tras_b == antes - 1 and monto == "65.00"
           and cita_tras["estado"] == "ATENDIDA")

    # ------------------------------------------------------------------ CP-29
    titulo("CP-29 — Cancelar una cita ya atendida")
    e, c = podologa.pedir("POST", f"/citas/{cita['id']}/cancelar/",
                          {"motivo": "Prueba CP-29: no debería poder cancelarse"})
    _, cita_tras = podologa.pedir("GET", f"/citas/{cita['id']}/", mostrar=False)
    anotar("CP-29", "rechazo (422) y la cita sigue ATENDIDA",
           f"HTTP {e} {codigo(c)}; cita {cita_tras['estado']}",
           e == 422 and cita_tras["estado"] == "ATENDIDA")

    # ------------------------------------------------------------------ CP-42
    titulo("CP-42 — Registro diario: día con atenciones y día sin atenciones")
    e, reg = podologa.pedir("GET", f"/reportes/registro-diario/?fecha={hoy}")
    suma = sum(float(a["monto_cobrado"] or 0) for a in reg["atenciones"])
    anotar("CP-42 con atenciones", "detalle con la atención de CP-32 y total = suma",
           f"HTTP {e}; {reg['cantidad']} atención(es); total {reg['total']}; suma {suma:.2f}",
           e == 200 and any(a["cita"] == cita["id"] for a in reg["atenciones"])
           and f"{suma:.2f}" == reg["total"])
    e, reg = podologa.pedir("GET", "/reportes/registro-diario/?fecha=2026-01-04")
    anotar("CP-42 sin atenciones", "cantidad 0 y total 0.00",
           f"HTTP {e}; cantidad {reg['cantidad']}; total {reg['total']}",
           e == 200 and reg["cantidad"] == 0 and reg["total"] == "0.00")

    # ------------------------------------------------------------ CP-07 / DEF-12
    titulo("CP-07 / DEF-12 — La única administradora: cambio de rol, desactivación y sedes_ids")
    _, usuarios = admin.pedir("GET", "/usuarios/", mostrar=False)
    usuarios = {u["correo"]: u for u in lista(usuarios)}
    gerencia, zapata = usuarios["gerencia@piessanos.pe"], usuarios["k.zapata@piessanos.pe"]
    e, c = admin.pedir("PATCH", f"/usuarios/{gerencia['id']}/", {"rol": "PODOLOGA"})
    anotar("CP-07 cambio de rol", "422 ultimo-administrador", f"HTTP {e} {codigo(c)}",
           e == 422 and codigo(c) == "ultimo-administrador")
    e, c = admin.pedir("PATCH", f"/usuarios/{gerencia['id']}/", {"esta_activo": False})
    _, gerencia_tras = admin.pedir("GET", f"/usuarios/{gerencia['id']}/", mostrar=False)
    anotar("CP-07 desactivar por PATCH", "no queda desactivada",
           f"HTTP {e}; esta_activo después = {gerencia_tras['esta_activo']}",
           gerencia_tras["esta_activo"] is True)
    e, c = admin.pedir("DELETE", f"/usuarios/{gerencia['id']}/")
    _, gerencia_tras = admin.pedir("GET", f"/usuarios/{gerencia['id']}/", mostrar=False)
    anotar("CP-07 desactivar por DELETE", "422 ultimo-administrador",
           f"HTTP {e} {codigo(c)}; esta_activo después = {gerencia_tras['esta_activo']}",
           e == 422 and gerencia_tras["esta_activo"] is True)
    e, c = admin.pedir("PATCH", f"/usuarios/{zapata['id']}/", {"sedes_ids": [cercado, bustamante]})
    sedes_tras = sorted(s["id"] for s in c.get("sedes", [])) if isinstance(c, dict) else None
    anotar("DEF-12 sedes_ids", "200 y las dos sedes asignadas",
           f"HTTP {e}; sedes {sedes_tras}",
           e == 200 and sedes_tras == sorted([cercado, bustamante]))
    admin.pedir("PATCH", f"/usuarios/{zapata['id']}/", {"sedes_ids": [bustamante]})

    # ------------------------------------------------------------------ DEF-13
    titulo("DEF-13 — Contraseña inicial al crear un usuario (P27) y primer ingreso")
    elegida = "ElegidaPorLaAdmin2026"  # nosec B105
    e, nuevo = admin.pedir("POST", "/usuarios/", {
        "correo": "prueba.p9@piessanos.pe", "nombres": "Prueba", "apellidos": "Práctica Nueve",
        "rol": "PODOLOGA", "sedes_ids": [cercado], "contrasena": elegida, "password": elegida})
    temporal = nuevo.get("contrasena_temporal") if isinstance(nuevo, dict) else None
    anotar("DEF-13 alta", "201", f"HTTP {e}; ¿devuelve contrasena_temporal? {bool(temporal)}",
           e == 201)
    usuario_nuevo = Cliente("usuario nuevo")
    e_elegida, _ = usuario_nuevo.entrar("prueba.p9@piessanos.pe", elegida)
    anotar("DEF-13 la admin define la contraseña", "entra con la contraseña que eligió la admin",
           f"HTTP {e_elegida}", e_elegida == 200)
    e_temp, c_temp = usuario_nuevo.entrar("prueba.p9@piessanos.pe", temporal or "")
    pendiente = c_temp.get("usuario", {}).get("debe_cambiar_contrasena") \
        if isinstance(c_temp, dict) else None
    e_bloq, c_bloq = usuario_nuevo.pedir("GET", "/pacientes/")
    e_cambio, _ = usuario_nuevo.pedir("POST", "/sesion/contrasena/", {
        "contrasena_actual": temporal, "contrasena_nueva": "NuevaDelUsuario2026",
        "confirmacion": "NuevaDelUsuario2026"})
    usuario_nuevo.sede = cercado
    e_despues, _ = usuario_nuevo.pedir("GET", "/pacientes/", mostrar=False)
    print(f"\n  GET /pacientes/ tras cambiar la contraseña -> HTTP {e_despues}")
    anotar("DEF-13 el usuario puede entrar",
           "entra y, tras cambiar la temporal, trabaja",
           f"temporal: HTTP {e_temp}, debe_cambiar={pendiente}; antes del cambio "
           f"HTTP {e_bloq} {codigo(c_bloq)}; cambio HTTP {e_cambio}; después HTTP {e_despues}",
           e_temp == 200 and e_cambio == 200 and e_despues == 200)

    # ------------------------------------------------------------ CP-10 / DEF-14
    titulo("CP-10 / DEF-14 — Horario de una sede nueva")
    e, sede_nueva = admin.pedir("POST", "/sedes/", {
        "nombre": "Sede Prueba P9", "direccion": "Calle de Prueba 9", "telefono": "054-000009",
        "horario": [{"dia_semana": 0, "hora_apertura": "09:00", "hora_cierre": "17:00"},
                    {"dia_semana": 5, "hora_apertura": "09:00", "hora_cierre": "12:00"}]})
    horarios = sede_nueva.get("horarios", []) if isinstance(sede_nueva, dict) else []
    abiertos = sorted(h["dia_semana"] for h in horarios if h.get("esta_abierta", True))
    anotar("CP-10 alta con horario", "201 con lunes y sábado abiertos",
           f"HTTP {e}; días abiertos {abiertos}", e == 201 and abiertos == [0, 5])
    e, c = admin.pedir("PATCH", f"/sedes/{sede_nueva['id']}/", {
        "horario": [{"dia_semana": 1, "hora_apertura": "08:00", "hora_cierre": "18:00"}]})
    abiertos = sorted(h["dia_semana"] for h in c.get("horarios", []) if h.get("esta_abierta", True))
    anotar("CP-10 edición del horario", "200 con solo el martes abierto",
           f"HTTP {e}; días abiertos {abiertos}", e == 200 and abiertos == [1])
    e, c = admin.pedir("PATCH", f"/sedes/{sede_nueva['id']}/", {
        "horario": [{"dia_semana": 2, "hora_apertura": "18:00", "hora_cierre": "08:00"}]})
    anotar("CP-10 cierre antes de apertura", "422 horario-invalido", f"HTTP {e} {codigo(c)}",
           e == 422 and codigo(c) == "horario-invalido")

    # ------------------------------------------------------------ CP-11 / DEF-15
    titulo("CP-11 / DEF-15 — Nombres repetidos y DELETE de sede o servicio con citas")
    e, c = admin.pedir("POST", "/sedes/", {"nombre": "Sede Cercado", "direccion": "Otra 1"})
    anotar("CP-11 sede repetida", "422 sede-duplicada", f"HTTP {e} {codigo(c)}",
           e == 422 and codigo(c) == "sede-duplicada")
    e, c = admin.pedir("POST", "/servicios/", {"nombre": "Quiropodia general",
                                               "duracion_minutos": 30, "precio": "10.00"})
    anotar("CP-11 servicio repetido", "422 servicio-duplicado", f"HTTP {e} {codigo(c)}",
           e == 422 and codigo(c) == "servicio-duplicado")
    e, _ = admin.pedir("DELETE", f"/sedes/{cercado}/")
    anotar("CP-11 DELETE sede con citas", "405 (sin DELETE; la baja es desactivar)",
           f"HTTP {e}", e == 405)
    e, _ = admin.pedir("DELETE", f"/servicios/{cita['servicio']}/")
    anotar("CP-11 DELETE servicio con citas", "405 (sin DELETE; la baja es desactivar)",
           f"HTTP {e}", e == 405)

    # ------------------------------------------------------------ CP-13 / DEF-16
    titulo("CP-13 / DEF-16 — Duración del servicio: 9, 10, 240 y 241 minutos")
    creados = {}
    for minutos, esperado in [(9, 422), (10, 201), (240, 201), (241, 422)]:
        e, c = admin.pedir("POST", "/servicios/", {
            "nombre": f"Servicio de prueba P9 ({minutos} min)", "duracion_minutos": minutos,
            "precio": "10.00"})
        if e == 201:
            creados[minutos] = c["id"]
        anotar(f"CP-13 {minutos} min", f"{esperado}", f"HTTP {e} {codigo(c) or ''}".strip(),
               e == esperado)

    # ------------------------------------------------------------ CP-25 / DEF-17
    titulo("CP-25 / DEF-17 — Cita en una sede o con un servicio inactivo")
    lucia = next(u for u in lista(admin.pedir("GET", "/usuarios/", mostrar=False)[1])
                 if u["correo"] == "podologa@piessanos.pe")
    manana = date.today() + timedelta(days=1)
    while manana.weekday() >= 5:
        manana += timedelta(days=1)
    inicio = datetime(manana.year, manana.month, manana.day, 18, 15, tzinfo=LIMA).isoformat()
    servicio_corto = creados.get(10)
    admin.pedir("PATCH", f"/servicios/{servicio_corto}/", {"esta_activo": False})
    e, c = admin.pedir("POST", "/citas/", {
        "sede": cercado, "paciente": paciente["id"], "profesional": lucia["id"],
        "servicio": servicio_corto, "inicio": inicio})
    anotar("CP-25 servicio inactivo", "422 servicio-inactivo", f"HTTP {e} {codigo(c)}",
           e == 422 and codigo(c) == "servicio-inactivo")
    admin.pedir("PATCH", f"/sedes/{sede_nueva['id']}/", {"esta_activa": False})
    e, c = admin.pedir("POST", "/citas/", {
        "sede": sede_nueva["id"], "paciente": paciente["id"], "profesional": lucia["id"],
        "servicio": cita["servicio"], "inicio": inicio})
    anotar("CP-25 sede inactiva", "422 sede-inactiva", f"HTTP {e} {codigo(c)}",
           e == 422 and codigo(c) == "sede-inactiva")

    # --------------------------------------------------------------- resumen
    titulo("Resumen")
    for caso, esperado, obtenido, veredicto in RESULTADOS:
        print(f"{veredicto:<12} | {caso:<32} | esperado: {esperado} | obtenido: {obtenido}")


if __name__ == "__main__":
    principal()
