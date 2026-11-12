# Imagen de Nginx con la SPA ya compilada dentro. Así el servidor no necesita
# Node ni una carpeta dist hecha a mano: basta con construir la imagen.
FROM node:22.12-alpine AS compilacion
WORKDIR /spa
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

FROM nginx:1.27-alpine
COPY infra/nginx/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=compilacion /spa/dist /var/www/spa
