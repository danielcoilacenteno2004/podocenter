# Defectos y observaciones de la ejecución de la Práctica 9 (18/11/2026)

Toda la evidencia de `docs/pruebas/` se obtuvo sobre el commit `7071027`, más el comando
`sembrar_volumen` y sus pruebas, con Python 3.12.13 y PostgreSQL 18.1 local (el informe declara
PostgreSQL 17; en esta máquina no hay Docker para levantar el contenedor). No se corrigió
código de la aplicación durante la ejecución.

## DEF-P9-01 · CP-03: no hay bloqueo tras intentos fallidos

- **Qué se hizo:** cinco `POST /api/v1/sesion/ingresar/` seguidos con contraseñas erróneas
  para `podologa@piessanos.pe` y, de inmediato, un sexto con la correcta (`casos_api.py`).
- **Qué se esperaba:** un bloqueo temporal de la cuenta después del quinto intento.
- **Qué pasó:** los cinco intentos respondieron 401 y el sexto, 200: entró. En el código no
  hay limitación de intentos ni bloqueo. Evidencia: `06_casos.txt`, sección CP-03.

## OBS-P9-02 · DEF-13: la administradora no define la contraseña inicial

- **Qué se hizo:** `POST /api/v1/usuarios/` con los campos `contrasena` y `password` y,
  después, un intento de ingreso con esa contraseña.
- **Qué se esperaba:** que el usuario nuevo entrara con la contraseña elegida por la
  administradora.
- **Qué pasó:** el servidor ignora esos campos y genera una contraseña temporal
  (`contrasena_temporal`). Con la elegida, el ingreso responde 401. Con la temporal entra,
  queda bloqueado hasta cambiarla (422 `cambio-de-contrasena-pendiente`) y, tras el cambio,
  trabaja con normalidad. El defecto se cerró con otra solución (commits `09ceaba` y `0bd3c47`).

## DEF-P9-03 · npm audit: vulnerabilidades en las dependencias del frontend

- **Qué se hizo:** `npm audit` y `npm audit --omit=dev` en `frontend/` (`05_seguridad.txt`).
- **Qué se esperaba:** cero vulnerabilidades conocidas, como en Python.
- **Qué pasó:** hay 11 en total (2 bajas, 3 moderadas, 4 altas y 2 críticas). En producción
  quedan 3 altas: `axios` 1.7.9 y `vue` 3.5.13 (a través de `@vue/server-renderer`). Las
  críticas (`tinypool`, a través de `vitest`) son solo de desarrollo. `pip-audit`, `bandit` y
  `check --deploy` salieron limpios.

## DEF-P9-05 · ZAP: falta la cabecera Content-Security-Policy, también en producción

- **Qué se hizo:** escaneo baseline de ZAP 2.17.0 (araña, araña AJAX y escaneo pasivo) contra
  http://localhost:5173 con la sesión de la administradora (`zap.py`, `04_zap.html`, `04_zap.txt`).
- **Qué se esperaba:** ninguna alerta de riesgo medio o alto.
- **Qué pasó:** no hubo alertas altas. Hubo 3 medias, 3 bajas y 3 informativas. El escaneo se
  hizo contra el servidor de desarrollo (Vite y Django con `DEBUG=True`), así que varias
  alertas dependen de ese entorno. Contrastadas con la configuración de producción:
  - **CSP no definida (media):** tampoco la define `infra/nginx/nginx.conf`. **Aplica a producción.**
  - **Falta X-Frame-Options (media) y X-Content-Type-Options (baja):** producción sí las pone
    (`nginx.conf` y `config/settings/prod.py`). No aplica a producción.
  - **Cross-Domain Misconfiguration (media):** CORS abierto de la configuración de desarrollo
    (`CORS_PERMITIR_TODO = True` en `dev.py`). Hay que revisarlo en producción.
  - **La cabecera Server muestra la versión (baja):** `nginx.conf` no tiene `server_tokens off`,
    así que es probable que también ocurra en producción. No se midió.
  - **Cookie sin HttpOnly (baja):** es `csrftoken`, que Django deja legible a propósito para que
    la SPA mande el token. La de sesión sí es HttpOnly en producción (`SESSION_COOKIE_HTTPONLY`).

## DEF-P9-07 · Móvil (390 px): el inventario no se puede usar y tres pantallas desbordan

- **Qué se hizo:** recorridos de `recorridos.cjs` en Chromium emulando un móvil de 390 × 844 px,
  táctil (`07_recorridos.txt`, `capturas/movil/`).
- **Qué se esperaba:** los mismos pasos que en escritorio y ninguna pantalla más ancha que la ventana.
- **Qué pasó:**
  - En P12 (Inventario), los botones «Movimiento» y «Ver disponibilidad» de cada fila quedan
    fuera de la pantalla: el botón de Gasa estéril está en x = 457 px de 390. Al desplazarse,
    la celda de la unidad («paquete») se le superpone y recibe el toque. Playwright informa
    `<td>paquete</td> intercepts pointer events`. **En móvil no se puede registrar un
    movimiento ni ver la disponibilidad entre sedes (P13 y P14) desde la tabla.**
    Captura: `capturas/movil/06-registrar-movimiento.png`.
  - Ancho de página medido contra los 390 px de la ventana: `/inventario` 725 px, `/pacientes`
    469 px y `/registro-diario` 425 px (con una atención en la tabla). `/panel` y `/agenda`
    caben. Captura: `capturas/movil/10-ancho-de-las-pantallas.png`.
  - En escritorio (Chromium y WebKit, 1366 px) los diez pasos pasan y ninguna pantalla desborda.

## OBS-P9-08 · RNF02: 4 interacciones desde la cuadrícula, no 3

- **Qué se hizo:** registro de una atención desde la agenda del día en la vista con que abre
  (cuadrícula), contando cada acción: pulsar la cita, «Registrar atención», escribir la
  observación y «Confirmar atención». El monto y los insumos se aceptaron tal como vienen.
- **Qué se esperaba:** las 3 interacciones que registra `docs/ESTADO.md` (medidas el 12/11).
- **Qué pasó:** fueron **4 en los tres navegadores**, dentro del límite de 5. La cuadrícula añade
  un paso, porque pulsar la cita abre el panel «Cita elegida» y el enlace está ahí. En la vista
  de lista, el botón «Registrar atención» está en la propia fila, que es el camino de 3
  interacciones medido el 12/11 (hoy no se volvió a medir). P11 sí pide el monto (precargado:
  70.00) y los insumos (precargado: 1, el habitual del servicio).

## INC-P9-04 · Corrida de carga descartada (error del script de prueba, no de la aplicación)

- **Qué se hizo:** primera corrida de `carga_rnf04.js` y `carga_atencion.js`.
- **Qué pasó:** fallaron el 98 % de las peticiones. La causa es que k6 vacía las cookies al
  empezar cada iteración, así que solo la primera petición de cada usuario llevaba la sesión.
  Se corrigió con `noCookiesReset: true` en los dos scripts y la carga se repitió. La corrida
  fallida se conserva en `03_carga_descartada.txt`.

## INC-P9-06 · Corrida de carga interrumpida por la suspensión del equipo

- **Qué se hizo:** corrida de `carga.sh` sobre el commit `7071027`, a las 14:49.
- **Qué pasó:** a las 14:51:28 Windows puso el equipo en suspensión moderna por batería (evento
  506 de Kernel-Power: «Austerity Battery Drain Budget Exceeded») y lo reanudó a las 15:56:35, al
  abrir la tapa (evento 507). Los escalones de 1 y 5 usuarios terminaron, pero los de 10 y 20 solo
  hicieron 4 y 2 peticiones, y k6 salió con un error del ejecutor. No es un fallo de la
  aplicación ni del script. La corrida se conserva en `03_carga_interrumpida.txt` y se repitió
  con el equipo conectado a la corriente.

## INC-P9-09 · Primeras corridas de los recorridos (errores del script, no de la aplicación)

Las dos primeras corridas de `recorridos.cjs` fallaron por el propio script, y se corrigió antes
de la corrida que queda en `07_recorridos.txt`:

- Buscaba la cita por su hora en 24 horas, pero la lista la escribe en 12 («04:06 p. m.»).
  Ahora la busca por paciente, servicio y estado.
- La agenda recuerda la última vista, y el paso de cancelar la dejaba en «Lista». Ahora se
  vuelve a la cuadrícula antes de contar las interacciones, y ese clic no se cuenta.
- Leía el título de la ficha antes de que se pintara, y esperaba una tabla de historial que no
  existe cuando el paciente no tiene atenciones.
- Medía el desborde contra `innerWidth`, que en un móvil emulado crece con el contenido. Ahora
  se mide contra los 390 px configurados.

## Corrección del 26/11/2026 (rama `feat/rf16-rf07-rf18`, sin commit)

Evidencia en `docs/pruebas/evidencia/`, con sufijo `-correccion`.

- **DEF-P9-01 (CP-03), corregido.** Al quinto intento fallido seguido, la cuenta queda
  bloqueada 15 minutos y no entra ni con la contraseña correcta, por la API y por `/admin/`.
  Pruebas en `backend/apps/usuarios/tests/test_bloqueo_de_ingreso.py`.
- **DEF-P9-03, corregido.** `npm audit` sin vulnerabilidades tras subir `axios`, `vue`,
  `vite`, `vitest` y `eslint` (ver `docs/ESTADO.md`).
- **DEF-P9-05, corregido en lo que aplica a producción.** `infra/nginx/nginx.conf` declara la
  CSP y `server_tokens off`. Corrección a lo dicho arriba: la alerta «Cross-Domain
  Misconfiguration» no viene de `CORS_PERMITIR_TODO`, que ningún código usa, sino del servidor
  de desarrollo de Vite. Django no envía cabeceras CORS (comprobado el 26/11), así que en
  producción no aplica.
- **DEF-P9-07 (390 px), sigue abierto.**

