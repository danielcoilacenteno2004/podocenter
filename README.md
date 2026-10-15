# PodoCenter — Sistema de gestión para centros de podología

Proyecto de Fin de Carrera — Ingeniería de Sistemas, Universidad Católica de Santa María.
Equipo: Coila Centeno, Sergio Daniel · Huaroc Condori, Andre Nicolas.

Sistema web multi-sede y multi-centro (SaaS) para la gestión de pacientes, citas,
atenciones e inventario de un centro de podología.

## Estructura

    backend/     API REST (Django 5 + Django REST Framework), organizada en capas
    frontend/    Cliente SPA (Vue 3 + Pinia + Vite)
    infra/       Docker Compose, Dockerfile y configuración de Nginx
    docs/        Convenciones de código y bitácora de sprints
    .github/     Pipeline de integración continua

## Puesta en marcha (desarrollo)

    docker compose -f infra/docker-compose.yml up -d db
    cd backend && python manage.py migrate && python manage.py runserver

## Documentación

- `docs/CONVENCIONES.md` — convención de codificación del equipo
- `docs/bitacora/` — bitácora de avance por sprint
