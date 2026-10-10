#!/bin/sh
# Primera emisión del certificado HTTPS (Let's Encrypt). Ejecutar UNA vez, con el DNS ya apuntando al VPS.
# Uso: ./deploy/init-letsencrypt.sh
set -e

COMPOSE="docker compose -f docker-compose.prod.yml --env-file .env"
DOMAIN=$(grep -E '^DOMAIN=' .env | cut -d= -f2-)
EMAIL=$(grep -E '^LETSENCRYPT_EMAIL=' .env | cut -d= -f2-)
[ -n "$DOMAIN" ] || { echo "Define DOMAIN en .env"; exit 1; }
[ -n "$EMAIL" ] || { echo "Define LETSENCRYPT_EMAIL en .env"; exit 1; }

echo ">> 1/4 Creando certificado temporal para que Nginx pueda arrancar..."
$COMPOSE run --rm --entrypoint "sh -c \"mkdir -p /etc/letsencrypt/live/$DOMAIN && \
  openssl req -x509 -nodes -newkey rsa:2048 -days 1 \
  -keyout /etc/letsencrypt/live/$DOMAIN/privkey.pem -out /etc/letsencrypt/live/$DOMAIN/fullchain.pem -subj '/CN=localhost'\"" certbot

echo ">> 2/4 Levantando la aplicación y Nginx..."
$COMPOSE up -d --build db app nginx

echo ">> 3/4 Pidiendo el certificado real a Let's Encrypt..."
$COMPOSE run --rm --entrypoint "sh -c \"rm -rf /etc/letsencrypt/live/$DOMAIN /etc/letsencrypt/archive/$DOMAIN /etc/letsencrypt/renewal/$DOMAIN.conf && \
  certbot certonly --webroot -w /var/www/certbot -d $DOMAIN -d www.$DOMAIN \
  --email $EMAIL --agree-tos --no-eff-email --force-renewal\"" certbot

echo ">> 4/4 Recargando Nginx y levantando todo..."
$COMPOSE exec nginx nginx -s reload
$COMPOSE up -d
echo "Listo: https://$DOMAIN"
