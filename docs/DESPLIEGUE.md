# Despliegue en un servidor

Cómo poner PodoCenter en marcha en la nube: un servidor Linux con Docker para
la aplicación y Nginx, y una base PostgreSQL gestionada.

> **Estado de esta guía (11/11/2026).** Los archivos que usa existen y se
> revisaron, pero **todavía no se ha ejecutado en un servidor real**, y las
> imágenes no se construyeron en la máquina de desarrollo porque no tiene
> Docker. Lo que sí está comprobado: `check --deploy` pasa con la
> configuración de producción y el pipeline la vuelve a revisar en cada
> cambio. La primera vez que se siga, hay que corregir aquí lo que no
> coincida.

## 1. Lo que hace falta

- Un servidor Linux con Docker Engine y el complemento `docker compose`,
  con los puertos 80 y 443 abiertos.
- Un dominio cuyo registro A apunte a ese servidor.
- PostgreSQL 17 (el que usan el desarrollo y el pipeline), de preferencia
  gestionado. La base no va en un contenedor: el compose de producción solo
  lleva la aplicación y Nginx.

## 2. Base de datos

El aislamiento entre centros vive en la base (políticas de seguridad por
fila). **Un superusuario o un rol con `BYPASSRLS` se las salta**, así que la
aplicación necesita un rol propio:

```sql
CREATE ROLE podo LOGIN PASSWORD '<contraseña larga>' NOSUPERUSER NOBYPASSRLS;
CREATE DATABASE podocenter OWNER podo;
```

Compruébelo conectado como ese rol; las dos columnas deben salir `f`:

```sql
SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname = current_user;
```

La migración de citas crea la extensión `btree_gist` (la usa la restricción
que impide dos citas solapadas). En el pipeline la crea un rol sin
`SUPERUSER` que es dueño de la base. Si su proveedor no lo permite, créela
una vez con el usuario administrador del servicio:

```sql
CREATE EXTENSION IF NOT EXISTS btree_gist;
```

## 3. Variables de entorno

```bash
cd infra/despliegue
cp .env.ejemplo .env
python3 -c "import secrets; print(secrets.token_urlsafe(64))"   # DJANGO_SECRET_KEY
python3 -c "import secrets; print(secrets.token_urlsafe(32))"   # CLAVE_CIFRADO_CAMPOS
```

Complete `.env` con esas dos claves, el dominio y los datos de la base. La
aplicación **no arranca** si falta alguna de las dos claves, si está vacía o
si conserva el texto de la plantilla.

`CLAVE_CIFRADO_CAMPOS` cifra los antecedentes y las observaciones clínicas.
**Guárdela fuera del servidor.** Si se pierde, esos datos no se pueden leer,
ni siquiera desde una copia de seguridad de la base.

## 4. Certificado HTTPS

Nginx espera el certificado en `infra/despliegue/certificados/`. La primera
vez, con Let's Encrypt y antes de levantar Nginx (el puerto 80 debe estar
libre):

```bash
docker run --rm -p 80:80 -v "$PWD/letsencrypt:/etc/letsencrypt" \
  certbot/certbot certonly --standalone -d <dominio> -m <correo> --agree-tos
mkdir -p certificados
cp -L letsencrypt/live/<dominio>/fullchain.pem letsencrypt/live/<dominio>/privkey.pem certificados/
```

## 5. Arranque

```bash
docker compose -f docker-compose.prod.yml up -d --build
```

- `api` construye la imagen de Django (`infra/Dockerfile`, Python 3.12) y,
  al arrancar, aplica las migraciones y recoge los estáticos antes de
  levantar gunicorn.
- `web` construye Nginx con la interfaz ya compilada
  (`infra/web.Dockerfile`), sirve la SPA y reenvía `/api` y `/admin`.

## 6. Primer acceso

Cree el administrador de plataforma, que es quien da de alta los centros:

```bash
docker compose -f docker-compose.prod.yml exec api python manage.py createsuperuser
```

Luego, en `https://<dominio>`:

1. Entre con esa cuenta y abra **Centros clientes**. Al dar de alta un centro
   se crea su administradora y la pantalla muestra **una sola vez** su
   contraseña temporal.
2. La administradora del centro entra con ella. El sistema la obliga a
   elegir una contraseña propia antes de hacer nada más.
3. En este orden:
   - **Sedes**: cada una con su horario de atención. Sin horario, la sede no
     admite citas.
   - **Servicios**: duración de 10 a 240 minutos y precio.
   - **Usuarios**: cada alta muestra una contraseña temporal para entregarla
     en persona.
   - **Inventario**: «+ Producto», una entrada de stock por sede y el mínimo
     de cada producto.

Si alguien olvida su contraseña, la administradora pulsa **Restablecer
contraseña** en Usuarios. No hay recuperación por correo (P23/P24).

## 7. Actualizar

```bash
git pull
docker compose -f docker-compose.prod.yml up -d --build
```

Las migraciones se aplican solas al arrancar `api`.

## 8. Renovar el certificado

Los certificados de Let's Encrypt vencen a los 90 días. Nginx ya sirve
`/.well-known/acme-challenge/` desde el volumen `certbot`, así que la
renovación no necesita detenerlo. El nombre del volumen lleva delante el del
proyecto de compose, que por defecto es el de la carpeta (`despliegue`):

```bash
docker run --rm -v despliegue_certbot:/var/www/certbot -v "$PWD/letsencrypt:/etc/letsencrypt" \
  certbot/certbot renew --webroot -w /var/www/certbot
cp -L letsencrypt/live/<dominio>/fullchain.pem letsencrypt/live/<dominio>/privkey.pem certificados/
docker compose -f docker-compose.prod.yml exec web nginx -s reload
```

## 9. Lo que no hace todavía

- No envía correos: ni activación de cuentas, ni recuperación de
  contraseña, ni recordatorios de citas (RF07).
- No tiene verificación en dos pasos (P02).
- Las copias de seguridad son las de la base gestionada. La aplicación no
  las programa.

## 10. No ejecutar en producción

`python manage.py cargar_demo` es para la exposición: borra y vuelve a crear
el centro de demostración «Pies Sanos» y crea cuentas cuya contraseña está
publicada en el repositorio. Con la configuración de producción se niega a
correr. Solo en un servidor montado para la exposición, sin centros reales,
se puede forzar con `--en-produccion`.
