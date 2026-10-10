# Nginx con los archivos estáticos del proyecto (CSS compilado, JS, íconos). Las fotos llegan por volumen.
FROM node:20-alpine AS css
WORKDIR /build
COPY package.json package-lock.json tailwind.config.js ./
RUN npm ci
COPY app/static/src app/static/src
COPY app/templates app/templates
COPY app/static/js app/static/js
RUN npm run build:css

FROM nginx:1.27-alpine
COPY app/static /usr/share/nginx/static
COPY --from=css /build/app/static/css/app.css /usr/share/nginx/static/css/app.css
COPY deploy/nginx/default.conf.template /etc/nginx/templates/default.conf.template
RUN rm -rf /usr/share/nginx/static/src && mkdir -p /usr/share/nginx/static/uploads /var/www/certbot
