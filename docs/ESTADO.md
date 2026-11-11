# Estado del proyecto

Corte: 10 de noviembre de 2026. Primera entrega comprometida: **12/11/2026**.

## 1. El riesgo principal

La Tabla 64 del informe compromete para el 12/11 lo siguiente, textualmente:

> «Usuarios y roles, Sedes, Pacientes con consentimiento, Citas sin
> recordatorios, **Atenciones y servicios**, desplegado **en producción** y
> **validado con la usuaria**.»

Contra eso, el estado real es:

| Compromiso | Estado |
|---|---|
| Usuarios y roles | Terminado |
| Sedes | Terminado |
| Pacientes con consentimiento | Terminado |
| Citas sin recordatorios | Terminado, con filtros y panel |
| Servicios | API terminada; **sin pantalla de gestión** |
| **Atenciones** | **Solo backend**: modelo, `POST /api/v1/atenciones/` y RLS. Sin pantalla P11, sin monto cobrado y sin insumos |
| Desplegado en producción | **No**: la infraestructura está escrita, nada corre en la nube |
| Validado con la usuaria | **No**: la prueba de usabilidad está diseñada, no aplicada |

Atenciones es el módulo que cierra el ciclo de la consulta y su pantalla P11 es
la que la Práctica N.° 7 llama «pantalla crítica»; es también donde se verifica
el RNF02. Sin él, el sistema registra citas pero no deja constancia de lo que
se hizo en ellas.

## 2. Lo que está sólido

- **115 pruebas**, **93.0 %** de cobertura de sentencias, sobre PostgreSQL
  real y no sobre una base en memoria. Una falla por la intercalación de la
  base: `test_el_listado_viene_ordenado_por_apellidos` compara con `sorted()`
  de Python, que pone «Álvarez» después de «Zapata».
- **Cero vulnerabilidades** conocidas en las dependencias tras subir a Django
  5.2 LTS, DRF 3.18.2, django-filter 25.2 y cryptography 50.0.2.
- `ruff` y `bandit` limpios.
- **Aislamiento multi-inquilino probado**: tres pruebas comprueban que un
  centro no ve, no abre y no modifica datos de otro. Es lo que sostiene el
  modelo de arriendo ante el jurado.
- **42 commits** con «un commit, un cambio», repartidos entre los dos
  integrantes.
- Entorno de demostración reproducible con un comando y probado con nueve
  pruebas, incluida una que verifica que las credenciales publicadas funcionan.

## 3. Brechas de diseño levantadas y no resueltas

Registradas en la Práctica N.° 7 y pendientes de decisión de alcance:

1. **Atención a domicilio.** El diseño no la distingue de la atención en
   consultorio, y el centro hace entre dos y tres visitas al día. Alcanza a
   P05, P06 y al modelo de datos.
2. **Lote y fecha de vencimiento de insumos.** No están modelados. Nada impide
   consumir una crema vencida en una atención. En insumos clínicos no es un
   detalle administrativo.
3. **Traslado de stock entre sedes.** El RF12 permite consultar la
   disponibilidad en la otra sede «sin fusionar los inventarios», así que mover
   stock está fuera de alcance. En la práctica alguien carga la caja, y hoy eso
   se registraría como una merma más una entrada: infla ambas y rompe la
   trazabilidad de la unidad.

## 4. Decisiones de alcance vigentes

| Código | Qué recortó |
|---|---|
| CC-12 | Tercer indicador del panel (stock), alerta automática del RF13, pantalla de reprogramación del RF08 |
| CC-18 | *Añade* la barra de filtros de la agenda |
| CC-19 | *Añade* el panel segmentado por decisión; no revierte CC-12 |
| RF07 | Recordatorios por mensajería, pendientes de aprobación del proveedor |

## 5. Lo que hay que decidir

- **Atenciones antes del 12/11**, o renegociar la Tabla 64 por escrito. Lo que
  no es defendible es dejar la fecha en el documento y no cumplirla.
- **El despliegue en producción** necesita una cuenta de nube real con tarjeta;
  no se resuelve escribiendo código.
- **La prueba de usabilidad** necesita una hora de la dueña y una de la
  podóloga. Es el requisito más barato de los tres y el que lleva más tiempo
  parado.
