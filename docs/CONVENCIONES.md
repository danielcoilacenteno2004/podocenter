# Convención de codificación

Acordada el 15/10/2026 por el equipo y verificada automáticamente por el
pipeline de integración continua. Lo que no puede comprobar una herramienta
está al final, en «Acuerdos que revisa una persona».

## 1. Idioma

| Elemento | Idioma | Ejemplo |
|---|---|---|
| Nombres del dominio (modelos, campos, servicios, variables) | Español | `Paciente`, `fecha_nacimiento`, `programar_cita` |
| Palabras reservadas y API del framework | Inglés (no se traduce) | `class Meta`, `get_queryset` |
| Comentarios y docstrings | Español | — |
| Mensajes de commit | Español | — |

El dominio es un centro de podología peruano y los requerimientos están en
español: traducir los nombres obliga a un diccionario mental en cada lectura.

## 2. Python

- Guía base: PEP 8 con línea de 100 caracteres.
- `snake_case` para funciones, variables y módulos; `PascalCase` para clases;
  `MAYUSCULAS` para constantes de módulo.
- Importaciones ordenadas por `ruff` (isort): estándar, terceros, `apps`/`config`.
- Toda función pública lleva docstring que explica **por qué**, no qué.
- Anotaciones de tipo en las firmas de los servicios; no son obligatorias
  en vistas ni serializadores.

## 3. Capas y dónde va cada cosa

| Capa | Archivo | Responsabilidad |
|---|---|---|
| Dominio | `models.py` | Entidades, restricciones de base de datos, propiedades derivadas |
| Aplicación | `servicios.py` | Reglas de negocio y transacciones; única capa que escribe |
| Presentación | `serializers.py`, `views.py` | Validación de forma, permisos y formato de respuesta |
| Infraestructura | `apps/core/` | Contexto de inquilino, auditoría, errores, campos cifrados |

Regla que no se negocia: **una vista nunca escribe en un modelo
directamente**. Si hay que crear, modificar o borrar, pasa por `servicios.py`.
Así la auditoría y las reglas no dependen de que alguien se acuerde.

## 4. Pruebas

- Un archivo de prueba por regla de negocio, no por clase.
- Nombre de la prueba en español, en forma de afirmación:
  `test_rechaza_una_cita_fuera_del_horario_de_atencion_de_la_sede`.
- Estructura preparar / ejecutar / comprobar, separada por líneas en blanco.
- Cobertura mínima del 80 %; el pipeline falla por debajo.

## 5. Control de versiones

- Ramas: `main` (desplegable), `develop` (integración), `feature/<módulo>-<tema>`.
- Mensaje de commit: `<tipo>(<módulo>): <qué cambia en imperativo>`.
  Tipos: `feat`, `fix`, `test`, `docs`, `refactor`, `chore`, `ci`.
  Ejemplo: `feat(citas): impedir el solape de citas con una restricción EXCLUDE`.
- Un commit = un cambio con sentido propio. Si el mensaje necesita una «y»,
  son dos commits.
- Ningún commit entra a `develop` con el pipeline en rojo.

## 6. JavaScript y Vue

- `camelCase` para variables y funciones; `PascalCase` para componentes.
- Un componente por archivo, con `<script setup>`.
- Las llamadas HTTP solo desde `services/`; los componentes no usan `axios`.
- El estado compartido vive en `stores/` (Pinia).

## 7. Acuerdos que revisa una persona

- Ningún secreto en el repositorio: todo por variable de entorno.
- Ningún dato real de paciente en las pruebas ni en los datos de ejemplo.
- Los mensajes de error que ve la usuaria se escriben en la capa de
  presentación y se redactan en segunda persona, sin jerga técnica.
