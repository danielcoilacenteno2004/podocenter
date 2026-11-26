# Evidencia de ejecución de las pruebas (Práctica N.° 9)

Capturas de la ejecución real de las pruebas del proyecto, hecha el **26/11/2026**
para usarlas como evidencia en la Práctica N.° 9 (Anexo B). Cada imagen es la salida de
un comando ejecutado ese día, convertida en PNG sin editarla.

- **Rama y commit:** `feat/rf16-rf07-rf18`, commit `1977d6c`. E01 a E03 se repiten en
  `7db1281`, el commit del 11/11; ver «El commit del 11/11» más abajo.
- **Entorno:**
  - Python 3.12.13.
  - PostgreSQL 18.1 local en el puerto 5433, con el rol `podo` sin `SUPERUSER` ni
    `BYPASSRLS`.
  - `config.settings.dev`, con Windows 11 como equipo.
  - No se usó producción ni ninguna cuenta de AWS. E09 usa la configuración de producción
    con valores ficticios.
- **Enmascarado:** contraseñas, claves, cookies, cadenas de conexión y direcciones IP
  aparecen como `****`. Lo hace `scripts/ejecutar.py` antes de guardar.

## Contenido

| Carpeta o archivo | Qué es |
|---|---|
| `texto/<ID>.txt` | Salida completa. La primera línea es el comando, la segunda la fecha y el commit, y la última el código de salida. |
| `img/` | **No está en el repositorio**: son 24 MB que se regeneran desde `texto/` con `bash docs/pruebas/evidencia/scripts/imagenes.sh`, y van completos en `evidencia_p9.zip`. |
| `img/<ID>.png` | La misma salida en imagen: fondo oscuro, fuente monoespaciada, 1400 px de ancho. A la izquierda va el número de línea del `.txt`, para que se vea que no falta ninguna. |
| `img/<ID>-a.png`, `-b`… | Partes de una salida larga, sin quitar líneas. |
| `img/<ID>-resumen.png` | Un tramo de la salida, por ejemplo el resumen final de pytest. El pie indica qué líneas muestra. |
| `img/E05-resumen.png`, `img/E12-resumen.png` | Varios resúmenes apilados para una sola figura del documento. Cada captura conserva su cabecera. |
| `img/E12-navegador/` | Capturas de pantalla de cada paso de los recorridos de Playwright. |
| `texto/E14-zap.html` | Informe completo de ZAP, con las cookies enmascaradas. |
| `indice.json` | Por captura: ID, comando, commit, fecha y hora, código de salida, resultado e imágenes. Incluye también la relación entre casos de la Tabla 7 y pruebas. |
| `scripts/` | Los scripts que generaron todo. No tocan código de la aplicación. |

## Resultados

| ID | Comando | Resultado |
|---|---|---|
| E01-1111 | `pytest -vv` en `7db1281` | 196 pruebas, 0 fallos |
| E01-actual | `pytest -vv` | 397 pruebas, 0 fallos |
| E02-1111 | `pytest --cov --cov-branch --cov-report=term-missing` en `7db1281` | Sentencias 95.20 % (1585 de 1665), ramas 84.62 % (176 de 208), combinada 94.02 % |
| E02-actual | `pytest --cov --cov-branch --cov-report=term-missing` | Sentencias 96.36 % (2861 de 2969), ramas 87.86 % (485 de 552), combinada 95.03 % |
| E03-1111 / E03-actual | Tabla por módulo del JSON de la misma corrida | El módulo más bajo es `pacientes`: 87.58 % y 90.20 % de sentencias |
| E04 | `pytest -vv -k 'aislamiento or otro_centro or otro_inquilino or rol_sin_privilegios'` | 22 pruebas, 0 fallos |
| E05-RF02 | `pytest -vv` de `test_api_permisos.py` y `test_sesion.py` | 21 pruebas, 0 fallos |
| E05-RF06 | `test_programar_cita.py`, `test_agenda_filtros.py` y `test_api_sin_escritura_directa.py` (citas) | 37 pruebas, 0 fallos |
| E05-RF10 | `test_registrar_atencion.py`, `test_api_atenciones.py` y `test_insumos.py` | 43 pruebas, 0 fallos |
| E05-RF11 | `test_inventario.py` y `test_productos_y_minimo.py` con `-k 'not disponibilidad'` | 33 pruebas, 0 fallos |
| E05-RF12 | `test_inventario.py -k disponibilidad` | 1 prueba, 0 fallos |
| E05-RF16 | `test_exportar_registro_diario.py` | 23 pruebas, 0 fallos |
| E05-RF18 | `test_cambiar_contrasena.py`, `test_totp.py` y `test_segundo_factor_*.py` | 54 pruebas, 0 fallos |
| E06 | `ruff check .`, `bandit --version` y `bandit -r backend -ll` | ruff sin hallazgos; bandit 1.9.4 sin hallazgos medios ni altos |
| E07 | `pip-audit -r requirements.txt` y `pip-audit` | Sobre `requirements.txt`, 0 vulnerabilidades. Sobre el entorno, 1: `pytest 8.3.4`, PYSEC-2026-1845, corregida en 9.0.3 |
| E08 | `npm audit` en `frontend/` | 11 vulnerabilidades: 2 críticas, 4 altas, 3 moderadas y 2 bajas |
| E09 | `manage.py check --deploy` con `config.settings.prod` y valores ficticios | Sin advertencias |
| E10 | `manage.py makemigrations --check --dry-run` | Sin cambios |
| E11 | `npm run lint` y `npm run build` | Lint sin errores; compilación correcta |
| E12-chromium | `cargar_demo` + `recorridos.cjs chromium` | 10 de 10 pasos OK; 4 interacciones para registrar la atención |
| E12-webkit | `cargar_demo` + `recorridos.cjs webkit` | 10 de 10 pasos OK |
| E12-movil | `cargar_demo` + `recorridos.cjs movil` (390 px) | 7 de 10 pasos OK |
| E13 | `cargar_demo`, `sembrar_volumen`, `k6 run carga_rnf04.js` | 10 de 10 umbrales: p95 de 222, 302, 327 y 344 ms por escalón y 336 ms en total; 0 de 1774 peticiones fallidas. Sobre 21 600 movimientos sembrados |
| E13-interrumpida, E13-interrumpida-2 | Lo mismo que E13 | Partidas por la suspensión del equipo: no valen como medida (ver abajo) |
| E14 | `cargar_demo` + ZAP baseline contra `localhost:5174` | 0 altas, 3 medias, 4 bajas y 3 informativas |

## Después de la corrección de DEF-25, DEF-26 y DEF-27 (26/11)

Mismos comandos, repetidos tras corregir los tres defectos, sobre el commit `1977d6c` con los
cambios todavía sin commit. Se guardan con el sufijo `-correccion`; las capturas anteriores se
conservan tal cual.

| ID | Comando | Resultado |
|---|---|---|
| E01-correccion | `pytest -vv` | 408 pruebas, 0 fallos |
| E02-correccion | `pytest --cov --cov-branch --cov-report=term-missing` | Sentencias 96.50 % (2921 de 3027), ramas 88.16 % (499 de 566), combinada 95.19 % |
| E03-correccion | Tabla por módulo | Ver la imagen |
| E05-DEF25-correccion | `pytest -vv` del bloqueo de ingreso y de la configuración de producción | 18 pruebas, 0 fallos |
| E06-correccion | `ruff check .` y `bandit -r backend -ll` | Sin hallazgos |
| E08-correccion | `npm audit` | 0 vulnerabilidades (eran 11) |
| E10-correccion | `makemigrations --check --dry-run` | Sin cambios |
| E11-correccion | `npm run lint` y `npm run build` | Lint sin errores; compilación correcta |
| E14-correccion | ZAP baseline contra `localhost:8088` | 0 altas, **0 medias**, 3 bajas y 3 informativas |

E14-correccion no se hizo contra Nginx, que no está instalado en este equipo. Se usó
`scripts/servidor_csp.py`, que sirve la SPA compilada con la CSP leída de
`infra/nginx/nginx.conf` y reenvía `/api` y `/admin` a Django. Las 3 bajas que quedan dependen de
ese servidor improvisado:
- No envía `X-Content-Type-Options`, que Nginx sí pone.
- Muestra su propia versión en la cabecera `Server`; en Nginx, `server_tokens off` la oculta.
- La cookie sin HttpOnly es `csrftoken`, que debe poder leerla la SPA.

El escaneo se repite contra producción antes del corte.

## Lo que falló o no salió como se esperaba

- **E12-movil, 3 pasos en FALLA.** Son los mismos 3 que en la ejecución del 18/11
  (`docs/pruebas/07_recorridos.txt`):
  - `/pacientes`, `/inventario` y `/registro-diario` son más anchos que la pantalla de
    390 px (469, 725 y 425 px).
  - Por eso no se alcanzan los botones de «registrar movimiento» y «disponibilidad».
  - El script termina con código 0 aunque haya pasos en FALLA; el resultado de cada paso
    está en la salida.
- **E08, `npm audit`:** 11 vulnerabilidades en las dependencias del cliente.
- **E07, `pip-audit` sobre el entorno completo:** encuentra `pytest 8.3.4`, una dependencia
  de desarrollo. El pipeline solo audita `requirements.txt`, que está limpio.
- **E14:** 3 alertas de riesgo medio: falta la CSP, Cross-Domain Misconfiguration y falta
  la cabecera anti-clickjacking. El escaneo se hizo contra el servidor de Vite; en
  producción esas cabeceras las pone Nginx y aquí no se midieron.
- **Primera corrida de E06, descartada.** Falló porque `ruff check .` encontró 3 hallazgos
  en los scripts de esta carpeta, recién escritos, no en el código de la aplicación. Se
  corrigieron los scripts y E06 se volvió a ejecutar; vale la última ejecución.

## Desviaciones respecto de lo pedido

- **`pytest -vv` en lugar de `-v`.** `pyproject.toml` añade `-q` a las opciones, y con `-v`
  la salida es un punto por prueba, no la lista de pruebas.
- **El filtro de E04 se ajustó a los nombres reales.** Ninguna prueba se llama «rls», y
  «centro» trae también las de alta y suspensión de centros, que no son de aislamiento.
- **El commit del 11/11 es `7db1281`, no `1d4d2af`.** `git log --until="2026-11-12" -1`
  devuelve `1d4d2af` (12/11 00:38), porque git toma la hora actual del día pedido. Ese
  commit tiene 294 pruebas. Se usó `7db1281` (11/11 18:22), el último cuyo
  `docs/ESTADO.md` registra «196 pruebas, 94.3 %», y la reejecución da 196 pruebas, 0
  fallos.
- **La cobertura del 11/11 no reproduce el 94.3 % que cita la Práctica 9.** La
  reejecución da 95.20 % de sentencias (94.02 % combinada con ramas).
  - La causa verificada es que `cargar_demo` decide qué citas sembrar según la hora: por
    ejemplo, `arranque.hour < 17`.
  - Entre la corrida del 25/11 a las 21:00 y la del 26/11 a las 08:49, sobre el mismo
    código, solo cambian 15 líneas de `cargar_demo.py`.
  - Por eso la rama actual da 96.36 % hoy y 95.86 % en `docs/ESTADO.md`.
  - Para el 11/11 es la explicación probable, pero no se reprodujo a la misma hora.
- **Duraciones de E01 a E05: no sirven como medida de rendimiento.** Hay dos razones:
  - Varias capturas corrieron en paralelo: E01-1111 junto con E06 a E11, y E01-actual y
    E02-actual junto con E12 y E14.
  - El equipo entró en suspensión (Modern Standby) varias veces, según el registro de
    eventos de Windows (Kernel-Power, eventos 506 y 507): de 08:34:24 a 08:41:47, de
    08:54:36 a 08:59:56, de 09:02:59 a 09:08:17 y de 09:11:19 a 09:19:07.
  - Por eso E01-1111 tardó 9 min 27 s y E02-1111, con la misma suite, 2 min 13 s; y
    E05-RF11, 5 min 19 s.
  - Lo que vale de esas capturas es el número de pruebas y de fallos.
- **E13 se ejecutó tres veces.** Las dos primeras quedaron partidas por una suspensión del
  equipo, que estaba con batería, y no valen como medida de rendimiento. Se conservan
  tal cual:
  - `texto/E13-interrumpida.txt`: suspensiones de 09:02:59 a 09:08:17 y de 09:11:19 a
    09:19:07.
  - `texto/E13-interrumpida-2.txt`: suspensión por inactividad de 09:24:00 a 09:32:14.
    El intento de impedirla no funcionó: en PowerShell 5.1, `0x80000003` es un entero
    negativo, y la llamada a `SetThreadExecutionState` fallaba sin que se notara.
  - La que vale es E13. Se corrió con `scripts/carga_despierto.ps1`, que impide la
    suspensión mientras dura la prueba sin cambiar la configuración de energía, y sin
    ninguna otra prueba en paralelo.
- **E12 corrió en el puerto 5174.** El 5173 estaba ocupado por otro proceso. Se usó una
  copia de `recorridos.cjs` que solo cambia la carpeta de las capturas, para no
  sobrescribir las del 18/11.
- **E14 activó el segundo factor de `gerencia@piessanos.pe`.** Con RF18 la administradora
  necesita el segundo factor para usar la API, así que `zap_evidencia.py` lo da de alta en
  la base local de prueba: pide el secreto, calcula el código TOTP y lo confirma. No se
  muestra el secreto ni los códigos.

## Lo que no se pudo ejecutar

Todo lo pedido se ejecutó. WebKit, k6 y ZAP estaban instalados.

## Cómo repetirlo

Desde la raíz del repositorio, con Python 3.12 activo, `POSTGRES_PORT` apuntando a la base
local de prueba y, para E12 a E14, Django en `127.0.0.1:8000` y Vite en `localhost:5174`:

```bash
bash docs/pruebas/evidencia/scripts/suite.sh "$(pwd -W)" -actual DIR_TEMPORAL "rama actual"
bash docs/pruebas/evidencia/scripts/calidad.sh
bash docs/pruebas/evidencia/scripts/requisitos.sh
bash docs/pruebas/evidencia/scripts/navegador.sh RUTA_A_NODE_MODULES_CON_PLAYWRIGHT
bash docs/pruebas/evidencia/scripts/carga.sh
python docs/pruebas/evidencia/scripts/ejecutar.py E14 --cwd . -- "python backend/manage.py cargar_demo" "python docs/pruebas/evidencia/scripts/zap_evidencia.py DIR_TEMPORAL"
python docs/pruebas/evidencia/scripts/render.py ID [--desde N --hasta M --nombre X]
python docs/pruebas/evidencia/scripts/indice.py
```
