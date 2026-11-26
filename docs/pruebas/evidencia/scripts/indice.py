"""Evidencia de la Práctica 9: arma indice.json a partir de registro.jsonl y de los textos.

    python docs/pruebas/evidencia/scripts/indice.py

El resultado en una línea de cada captura se lee del propio texto (la línea de
resumen de pytest, de ruff, de bandit, de pip-audit, de npm, de k6 o de ZAP); no
se escribe a mano. Las imágenes se asocian por el prefijo del identificador.
"""
# La tabla CASOS lleva nombres completos de pruebas, que no se pueden partir.
# ruff: noqa: E501
import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

AQUI = Path(__file__).resolve().parent.parent
RAIZ = AQUI.parents[2]

QUE = {
    "E01": "Suite completa del servidor",
    "E02": "Cobertura de sentencias y de ramas",
    "E03": "Cobertura por módulo",
    "E04": "Pruebas de aislamiento entre centros",
    "E05": "Pruebas por requerimiento crítico",
    "E06": "Análisis estático (ruff y bandit)",
    "E07": "Dependencias del servidor (pip-audit)",
    "E08": "Dependencias del cliente (npm audit)",
    "E09": "Configuración de producción (check --deploy, valores ficticios)",
    "E10": "Migraciones (makemigrations --check)",
    "E11": "Cliente web (lint y build)",
    "E12": "Usabilidad y compatibilidad (Playwright)",
    "E13": "Carga de la consulta entre sedes (RNF04, k6)",
    "E14": "Escaneo dinámico (OWASP ZAP baseline)",
}

# Relación caso → prueba. La Tabla 7 no nombra ninguna prueba: solo se anotan
# los casos cuya entrada y resultado esperado coinciden con lo que afirma una
# prueba automatizada concreta de la rama actual. Los demás casos se omiten.
T = "backend/apps"
CASOS = {
    "CP-02": [f"{T}/usuarios/tests/test_sesion.py::test_un_correo_inexistente_responde_igual_que_una_clave_errada",
              f"{T}/usuarios/tests/test_sesion.py::test_la_contrasena_errada_no_abre_la_sesion"],
    "CP-04": [f"{T}/core/tests/test_api_permisos.py::test_la_podologa_no_puede_listar_usuarios",
              f"{T}/core/tests/test_api_permisos.py::test_la_podologa_consulta_el_catalogo_pero_no_lo_edita"],
    "CP-05": [f"{T}/usuarios/tests/test_api_usuarios.py::test_un_correo_repetido_se_rechaza_antes_de_tocar_la_base"],
    "CP-06": [f"{T}/usuarios/tests/test_api_usuarios.py::test_no_se_puede_desactivar_al_ultimo_administrador",
              f"{T}/usuarios/tests/test_usuarios_y_roles.py::test_no_deja_al_centro_sin_administrador"],
    "CP-07": [f"{T}/usuarios/tests/test_editar_usuario.py::test_la_unica_administradora_no_pierde_el_rol"],
    "CP-08": [f"{T}/usuarios/tests/test_cambiar_contrasena.py (9 pruebas)"],
    "CP-11": [f"{T}/sedes/tests/test_api_sedes.py::test_un_nombre_repetido_es_error_de_negocio_y_no_500",
              f"{T}/catalogo/tests/test_api_servicios.py::test_un_nombre_repetido_es_error_de_negocio_y_no_500"],
    "CP-13": [f"{T}/catalogo/tests/test_api_servicios.py::test_la_duracion_fuera_de_10_a_240_se_rechaza[5|9|241]",
              f"{T}/catalogo/tests/test_api_servicios.py::test_la_base_tambien_impide_una_duracion_fuera_de_rango"],
    "CP-15": [f"{T}/pacientes/tests/test_registro_paciente.py::test_registra_el_paciente_con_su_consentimiento_en_la_misma_operacion"],
    "CP-16": [f"{T}/pacientes/tests/test_registro_paciente.py::test_rechaza_un_segundo_paciente_con_el_mismo_documento"],
    "CP-17": [f"{T}/pacientes/tests/test_registro_paciente.py::test_no_registra_un_paciente_sin_consentimiento_de_tratamiento_de_datos"],
    "CP-19": [f"{T}/pacientes/tests/test_registro_paciente.py::test_los_antecedentes_se_guardan_cifrados_en_la_columna"],
    "CP-20": [f"{T}/pacientes/tests/test_api_sin_escritura_directa.py::test_los_antecedentes_no_se_cambian_por_fuera_del_servicio"],
    "CP-22": [f"{T}/citas/tests/test_programar_cita.py::test_rechaza_una_segunda_cita_que_se_solapa_con_la_misma_profesional",
              f"{T}/citas/tests/test_programar_cita.py::test_la_base_de_datos_impide_el_solape_aunque_se_salte_la_capa_de_servicios"],
    "CP-23": [f"{T}/citas/tests/test_programar_cita.py::test_rechaza_una_cita_fuera_del_horario_de_atencion_de_la_sede"],
    "CP-24": [f"{T}/citas/tests/test_programar_cita.py::test_rechaza_una_cita_en_el_pasado"],
    "CP-25": [f"{T}/citas/tests/test_programar_cita.py::test_una_sede_desactivada_no_admite_citas_nuevas",
              f"{T}/citas/tests/test_programar_cita.py::test_un_servicio_desactivado_no_admite_citas_nuevas"],
    "CP-26": [f"{T}/citas/tests/test_api_sin_escritura_directa.py (3 pruebas)"],
    "CP-27": [f"{T}/citas/tests/test_agenda_filtros.py::test_el_filtro_por_estado_acota_la_jornada",
              f"{T}/citas/tests/test_agenda_filtros.py::test_el_filtro_por_servicio_acota_la_jornada",
              f"{T}/citas/tests/test_agenda_filtros.py::test_el_filtro_por_profesional_acota_la_jornada",
              f"{T}/citas/tests/test_agenda_filtros.py::test_los_filtros_se_combinan",
              f"{T}/citas/tests/test_agenda_filtros.py::test_una_fecha_mal_escrita_se_rechaza_con_su_codigo"],
    "CP-31": [f"{T}/atenciones/tests/test_registrar_atencion.py::test_rechaza_registrar_la_atencion_de_una_cita_que_todavia_no_llega"],
    "CP-32": [f"{T}/atenciones/tests/test_insumos.py::test_la_atencion_descuenta_el_stock_y_deja_una_salida_por_insumo",
              f"{T}/atenciones/tests/test_insumos.py::test_sin_stock_suficiente_no_se_registra_nada"],
    "CP-33": [f"{T}/atenciones/tests/test_registrar_atencion.py::test_otro_centro_no_ve_la_atencion_aunque_consulte_sin_filtrar"],
    "CP-34": [f"{T}/inventario/tests/test_inventario.py::test_una_entrada_suma_al_stock_de_la_sede"],
    "CP-35": [f"{T}/inventario/tests/test_inventario.py::test_una_merma_resta_del_stock"],
    "CP-36": [f"{T}/inventario/tests/test_inventario.py::test_una_merma_no_puede_dejar_el_stock_en_negativo",
              f"{T}/inventario/tests/test_inventario.py::test_la_base_impide_un_stock_negativo_aunque_se_salte_el_servicio"],
    "CP-37": [f"{T}/inventario/tests/test_inventario.py::test_la_salida_por_consumo_no_se_registra_a_mano",
              f"{T}/inventario/tests/test_inventario.py::test_un_movimiento_sin_sede_se_rechaza_con_su_codigo",
              f"{T}/inventario/tests/test_inventario.py::test_un_movimiento_sin_producto_se_rechaza_con_su_codigo"],
    "CP-38": [f"{T}/inventario/tests/test_inventario.py::test_la_disponibilidad_muestra_todas_las_sedes_del_centro"],
    "CP-40": [f"{T}/inventario/tests/test_productos_y_minimo.py::test_un_minimo_invalido_se_rechaza[-1]",
              f"{T}/inventario/tests/test_productos_y_minimo.py::test_el_minimo_de_la_sede_decide_bajo_minimo_y_queda_auditado"],
    "CP-41": [f"{T}/inventario/tests/test_inventario.py::test_otro_centro_no_ve_productos_stock_ni_movimientos",
              f"{T}/inventario/tests/test_inventario.py::test_las_pruebas_de_aislamiento_corren_con_un_rol_sin_privilegios"],
    "CP-42": [f"{T}/atenciones/tests/test_registro_diario.py::test_lista_las_atenciones_del_dia_con_su_monto_y_el_total",
              f"{T}/atenciones/tests/test_registro_diario.py::test_un_dia_sin_atenciones_da_total_cero"],
    "CP-43": [f"{T}/citas/tests/test_agenda_filtros.py::test_el_ingreso_esperado_excluye_las_citas_canceladas",
              f"{T}/citas/tests/test_agenda_filtros.py::test_el_ingreso_confirmado_es_lo_cobrado_y_cuadra_con_el_registro_diario",
              f"{T}/citas/tests/test_agenda_filtros.py::test_la_ocupacion_se_mide_contra_el_horario_de_la_sede"],
    "CP-44": [f"{T}/core/tests/test_api_centros.py::test_el_alta_crea_el_centro_con_su_administrador_listo_para_entrar"],
    "CP-45": [f"{T}/core/tests/test_api_centros.py::test_un_centro_suspendido_no_puede_iniciar_sesion",
              f"{T}/core/tests/test_api_centros.py::test_al_reactivar_el_centro_sus_usuarios_vuelven_a_entrar"],
    "CP-46": [f"{T}/core/tests/test_aislamiento_multi_centro.py::test_una_peticion_sin_centro_no_hereda_el_centro_de_la_anterior"],
    "CP-53": [f"{T}/atenciones/tests/test_exportar_registro_diario.py::test_el_total_exportado_es_el_mismo_que_el_de_la_pantalla"],
    "CP-54": [f"{T}/atenciones/tests/test_exportar_registro_diario.py::test_un_rango_sin_atenciones_exporta_un_archivo_con_total_cero[pdf|xlsx]"],
    "CP-55": [f"{T}/usuarios/tests/test_segundo_factor_alta.py::test_confirmar_con_un_codigo_valido_activa_el_factor_y_entrega_diez_codigos",
              f"{T}/usuarios/tests/test_segundo_factor_ingreso.py::test_un_codigo_valido_completa_el_ingreso_y_queda_en_la_auditoria"],
    "CP-56": [f"{T}/usuarios/tests/test_segundo_factor_ingreso.py::test_la_contrasena_sola_no_abre_la_sesion_de_una_cuenta_con_factor"],
    "CP-57": [f"{T}/usuarios/tests/test_segundo_factor_alta.py::test_confirmar_con_un_codigo_valido_activa_el_factor_y_entrega_diez_codigos"],
}


def ultima(patron: str, texto: str) -> str | None:
    hallados = re.findall(patron, texto, flags=re.M)
    return hallados[-1].strip() if hallados else None


def resultado(id_: str, texto: str) -> str:
    base = id_.split("-")[0]
    if base in ("E01", "E04", "E05"):
        r = ultima(r"^=+ (.*(?:passed|failed|error).*) =+$", texto)
        return r or "sin línea de resumen de pytest"
    if base == "E02":
        tot = ultima(r"^TOTAL\s+.*$", texto)
        s = ultima(r"^Sentencias:.*$", texto)
        r = ultima(r"^Ramas:.*$", texto)
        p = ultima(r"^\d+ passed.*$", texto)
        return f"{p}; {s}; {r}; fila {' '.join(tot.split())}"
    if base == "E03":
        return ultima(r"^Cobertura combinada.*$", texto) or ""
    if base == "E06":
        ruff = ultima(r"^(All checks passed!|Found \d+ errors?.*)$", texto)
        bandit = ultima(r"^\s*(No issues identified\.)$", texto) or "bandit con hallazgos"
        sev = re.search(r"Medium: (\d+)\s+High: (\d+)", texto.replace("\n", " ").replace("\t", " "))
        extra = f" (medios {sev.group(1)}, altos {sev.group(2)})" if sev else ""
        return f"ruff: {ruff}; bandit -ll: {bandit}{extra}"
    if base == "E07":
        partes = re.findall(r"^(No known vulnerabilities found|Found \d+ known vulnerabilit.*)$",
                            texto, flags=re.M)
        return "; ".join(f"{c}: {p}" for c, p in zip(
            ["-r requirements.txt", "entorno completo"], partes, strict=False))
    if base == "E08":
        return ultima(r"^\d+ vulnerabilities .*$", texto) or ultima(r"found 0 vulnerabilities", texto) or ""
    if base in ("E09", "E10"):
        return ultima(r"^(System check identified.*|No changes detected.*)$", texto) or ""
    if base == "E11":
        lint = "lint sin errores" if re.search(r"\$ npm run lint\n(?:.*\n)*?\[código de salida de este comando: 0\]", texto) else "lint con errores"
        build = ultima(r"^✓ built in .*$", texto) or "build sin línea final"
        return f"{lint}; {build}"
    if base == "E12":
        return ultima(r"^\[\w+\] resumen: .*$", texto) or ""
    if base == "E13":
        ths = re.findall(r"^\s*(✓|✗) '(.*?)'", texto, flags=re.M)
        ok = sum(1 for m, _ in ths if m == "✓")
        p95 = re.search(r"http_req_duration\{tipo:disponibilidad\}\s*\n\s*. 'p\(95\)<2000' "
                        r"p\(95\)=(\S+)", texto)
        # La primera aparición es la del total (TOTAL RESULTS); las siguientes, por escalón.
        total = re.search(r"^\s*http_req_failed\.+: (.*)$", texto, flags=re.M)
        fallos = " ".join(total.group(1).split()) if total else None
        r = f"{ok} de {len(ths)} umbrales cumplidos"
        r += f"; p95 global de la consulta {p95.group(1)}" if p95 else ""
        r += f"; peticiones fallidas {fallos}" if fallos else ""
        if "interrumpida" in id_:
            r = "INTERRUMPIDA por la suspensión del equipo, no vale como medida (" + r + ")"
        return r
    if base == "E14":
        niveles = re.findall(r"^\s+(Alto|Medio|Bajo|Informativo)\s+(\d+)$", texto, flags=re.M)
        return ", ".join(f"{n} {c}" for n, c in niveles)
    return ""


def version(cmd: list[str]) -> str:
    try:
        return subprocess.run(cmd, capture_output=True, text=True, check=False,  # noqa: S603
                              cwd=RAIZ).stdout.strip()
    except OSError as e:
        return f"no disponible: {e}"


def principal():
    sys.stdout.reconfigure(encoding="utf-8")
    registros = {}
    for linea in (AQUI / "registro.jsonl").read_text(encoding="utf-8").splitlines():
        if linea.strip():
            r = json.loads(linea)
            registros[r["id"]] = r  # la última ejecución de cada ID es la que vale
    # Cada imagen va con el ID más largo que la nombra: E13-interrumpida-a.png es de
    # E13-interrumpida, no de E13.
    de_id = {}
    for n in sorted(p.name for p in (AQUI / "img").glob("*.png")):
        candidatos = [i for i in registros if n == f"{i}.png" or n.startswith(f"{i}-")]
        if candidatos:
            de_id.setdefault(max(candidatos, key=len), []).append(n)
    capturas = []
    for id_, r in sorted(registros.items()):
        texto = (AQUI / r["texto"]).read_text(encoding="utf-8")
        capturas.append({
            "id": id_,
            "que": QUE.get(id_.split("-")[0], ""),
            "comando": r["comando"],
            "commit": r["commit"],
            "fecha_hora": r["fecha"],
            "codigo_salida": r["codigo_salida"],
            "codigos_por_comando": r["codigos_por_comando"],
            "resultado": resultado(id_, texto),
            "texto": r["texto"],
            "imagenes": [f"img/{n}" for n in de_id.get(id_, [])],
            "nota": r.get("etiqueta", ""),
        })
    pg = version([sys.executable, "-c",
                  "import psycopg,os;c=psycopg.connect(host='localhost',port=os.environ.get"
                  "('POSTGRES_PORT','5432'),user='podo',password=os.environ.get"
                  "('POSTGRES_PASSWORD','podo'),dbname='podocenter');"
                  "print(c.execute('select version()').fetchone()[0])"])
    indice = {
        "generado": datetime.now().astimezone().isoformat(timespec="seconds"),
        "rama": version(["git", "rev-parse", "--abbrev-ref", "HEAD"]),
        "commit_actual": version(["git", "rev-parse", "--short", "HEAD"]),
        "commit_11_11": "7db1281 (2026-11-11 18:22, último commit cuyo docs/ESTADO.md registra "
                        "196 pruebas y 94.3 %; ver LEEME.md)",
        "python": version([sys.executable, "--version"]),
        "postgresql": pg,
        "entorno": "Equipo local Windows 11; base PostgreSQL local de prueba (puerto 5433) con "
                   "el rol podo sin SUPERUSER ni BYPASSRLS; config.settings.dev. Sin "
                   "producción ni cuentas de AWS.",
        "capturas": capturas,
        "casos_a_pruebas": {
            "criterio": "La Tabla 7 no nombra pruebas. Se relacionan solo los casos cuya "
                        "entrada y resultado esperado coinciden con lo que afirma una prueba "
                        "automatizada concreta de la rama actual; el resto se omite.",
            "relacion": CASOS,
        },
    }
    (AQUI / "indice.json").write_text(json.dumps(indice, ensure_ascii=False, indent=2) + "\n",
                                      encoding="utf-8")
    for c in capturas:
        print(f"{c['id']:<14} {c['codigo_salida']:>3}  {c['resultado'][:150]}")


if __name__ == "__main__":
    principal()
