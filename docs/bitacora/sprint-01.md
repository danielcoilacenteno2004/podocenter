# Bitácora — Sprint 1

**Periodo:** 15/10/2026 – 21/10/2026
**Objetivo del sprint:** cerrar Usuarios y roles y Sedes, y dejar el
aislamiento multi-centro funcionando antes de tocar datos de pacientes.
**Capacidad planificada:** 2 integrantes × 28 h/semana = 8 días de línea base.

## Qué se implementó

| Actividad de la línea base | Avance | Evidencia |
|---|---|---|
| Usuarios y roles (5 días) | 100 % | `apps/usuarios`, 7 pruebas |
| Sedes (4 días) | 100 % | `apps/sedes`, horario por día (CC-15) |
| Despliegue en la nube (3 días) | 80 % | Imagen y pipeline; falta la configuración de producción |

- Modelo de usuario propio con el correo como credencial y bcrypt como
  algoritmo de hash.
- RBAC de tres roles con la restricción de base `ck_usuario_centro_segun_rol`:
  el administrador de plataforma no puede tener centro y los demás no pueden
  quedarse sin él.
- Aislamiento multi-inquilino con políticas de seguridad a nivel de fila (RLS)
  sobre siete tablas, más `FORCE ROW LEVEL SECURITY` para que no lo esquive ni
  el dueño de la tabla.
- Regla de negocio: no se puede desactivar al último administrador de un centro.

## Qué quedó pendiente

- Verificación en dos pasos (TOTP). El modelo ya tiene los campos
  (`segundo_factor_activo`, `secreto_totp`), pero el flujo de P02 no está.
- Recuperación de contraseña (P23 y P24), que entró como CC-17 en la Práctica
  N.° 7 y suma medio día a este módulo.
- Configuración de producción del despliegue.

## Desviaciones respecto al plan

1. **El RLS costó un día más de lo estimado.** No por las políticas en sí,
   sino porque `horario_sede` y `asignacion_sede` no llevan `centro_id`: su
   política tuvo que escribirse contra la tabla padre. Se decidió no
   denormalizar `centro_id` en esas dos tablas para no romper la 3FN que la
   Práctica N.° 6 documentó.
2. **La verificación en dos pasos se movió al Sprint 2.** Se priorizó cerrar
   el aislamiento, porque sin él ningún otro módulo puede escribirse con
   seguridad.

## Decisiones tomadas

- `btree_gist` se instala desde la migración de `citas`, no desde un script
  manual, para que el entorno de integración continua se levante solo.
- Las claves y secretos nunca entran al repositorio: el pipeline inyecta una
  clave propia y producción las recibe por variable de entorno.
