# PodoCenter — Proyecto de Fin de Carrera (UCSM)

Sistema de gestión multi-sede para un centro de podología, arrendable a otros
centros (multi-inquilino). Equipo: Sergio Daniel Coila Centeno y Andre Nicolas
Huaroc Condori. Asesor con sesiones de seguimiento; el proyecto se sustenta
ante un jurado.

## Lo que más importa de este repositorio

**La coherencia entre el código y los documentos es parte del entregable.** El
informe y las prácticas describen este repositorio con cifras concretas
(número de pruebas, cobertura, commits, versiones). Si cambias algo que esos
documentos afirman, hay que corregir el documento en el mismo turno. Los
documentos están en `docs/entregables/` y el inventario de afirmaciones
verificables, en `docs/COHERENCIA.md`.

**Nunca inventes datos.** El asesor ya objetó una vez la falta de fuentes
trazables. Toda cifra de una fuente externa lleva su referencia, y no se
atribuyen opiniones a la dueña del centro ni a la podóloga sin que las hayan
dicho de verdad.

## Arranque

```bash
# base de datos
docker compose -f infra/docker-compose.yml up -d        # PostgreSQL 17

# backend
python -m venv .venv && source .venv/bin/activate       # Python 3.12
pip install -r requirements.txt -r requirements-dev.txt
cd backend
export DJANGO_SETTINGS_MODULE=config.settings.dev
python manage.py migrate
python manage.py cargar_demo                            # datos de demostración
python manage.py runserver 127.0.0.1:8000

# frontend (otra terminal)
cd frontend && npm install && npm run dev               # http://localhost:5173
```

Cuentas del entorno de demostración, todas con la contraseña `Podocenter2026`:

| Correo | Rol |
|---|---|
| `gerencia@piessanos.pe` | Administradora del centro |
| `podologa@piessanos.pe` | Podóloga (ambas sedes) |
| `k.zapata@piessanos.pe` | Podóloga (una sede) |
| `plataforma@podocenter.pe` | Administrador de plataforma (`/admin/`) |

`cargar_demo` borra y rehace el centro de demostración; con `--conservar` no
toca nada si ya existe.

## Python 3.12, no otra versión

El proyecto **exige Python 3.12**. Es la versión de la imagen de producción
(`infra/Dockerfile`: `python:3.12-slim`), la del pipeline
(`.github/workflows/ci.yml`) y la que declara el informe (2.2). Las pruebas,
la cobertura y el análisis de seguridad que cita el informe se obtienen con
esa versión.

Con otra versión la verificación deja de ser fiable:

- `psycopg[binary]==3.2.3` no tiene binarios para Python 3.14: `pip install`
  falla y `pip-audit -r requirements.txt` también.
- `bandit` 1.8.0 en Python 3.14 se saltaba todos los archivos y terminaba con
  código 0, es decir, aprobaba en falso (corregido al subir a 1.9.4, que se
  comprobó contra un archivo deliberadamente inseguro en 3.12 y en 3.14).

Si en tu máquina hay otra versión, crea el entorno con 3.12 (por ejemplo,
`uv venv --python 3.12 .venv`) antes de dar por buena cualquier verificación.

## Verificación antes de dar algo por terminado

```bash
ruff check .                                   # estilo; debe salir limpio
bandit -c pyproject.toml -r backend/apps       # seguridad del código
pip-audit -r requirements.txt                  # dependencias vulnerables
pytest --cov --cov-fail-under=80               # 124 pruebas, cobertura ≥ 80 %
```

El pipeline rechaza un hallazgo sin corregir, una prueba en rojo, cobertura por
debajo del 80 %, un modelo cambiado sin su migración o una configuración
insegura de producción. Eso está declarado en el informe: si lo relajas, el
documento deja de ser cierto.

## Convenciones

- **Idioma del código en español**: modelos, campos, funciones, mensajes y
  nombres de prueba. Es deliberado y se mantiene.
- **Commits**: «un commit, un cambio». Si el mensaje necesita una «y», son dos
  commits. Autoría repartida entre los dos integrantes.
- **Pruebas**: cada una lleva un comentario que explica qué garantiza y por
  qué importa, no qué hace el código.
- **Errores de negocio**: se levantan como `ReglaDeNegocio(codigo, detalle)` y
  salen en formato RFC 9457 con un campo `codigo` estable que la interfaz
  traduce. Nunca un 500 ni un mensaje suelto.
- **Multi-inquilino**: el aislamiento vive en la base, con políticas de
  seguridad por fila sobre `app.centro_id`, no en el código de la aplicación.
  En pruebas y comandos hay que fijarlo con
  `apps.core.contexto_http.fijar_centro_en_la_sesion(centro_id)` o el ORM no
  verá ni podrá borrar nada.
- **Reglas de negocio en el servicio, no en la vista**: la agenda, el
  solapamiento y el horario de sede se deciden en `apps/citas/servicios.py`.
  El navegador solo pinta.

## Estado

Construido: Cuentas y centros, Usuarios y roles, Sedes con horario, Catálogo de
servicios, Pacientes con consentimiento versionado y antecedentes cifrados,
Citas con agenda filtrable y panel del día segmentado, Atenciones con su
pantalla P11 (sin monto ni insumos).

No construido: Inventario, Registro diario, Notificaciones
(RF07, pendiente de aprobación del proveedor de mensajería).

Frontend: 9 pantallas de las 29 diseñadas en la Práctica N.° 7 (P01, P03, P04, P05, P06, P07, P08, P10, P11); P21 solo cubre la página no encontrada.

El detalle, con lo que falta y lo que está en riesgo, en `docs/ESTADO.md`.
