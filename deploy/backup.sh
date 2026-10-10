#!/bin/sh
# Copia diaria: base de datos (pg_dump) + fotos (tar.gz). Se queda con los últimos BACKUP_RETENTION_DAYS días.
# Corre dentro del contenedor "backup". Restauración: ver DEPLOY.md.
set -eu

HOUR="${BACKUP_HOUR:-3}"
KEEP="${BACKUP_RETENTION_DAYS:-14}"

run_backup() {
  stamp=$(date +%Y%m%d-%H%M)
  echo "[$(date)] Iniciando copia $stamp"
  pg_dump -Fc -f "/backups/db-$stamp.dump"
  tar -czf "/backups/uploads-$stamp.tar.gz" -C /data uploads
  find /backups -type f \( -name 'db-*.dump' -o -name 'uploads-*.tar.gz' \) -mtime +"$KEEP" -delete
  echo "[$(date)] Copia lista: $(ls -1 /backups | wc -l) archivos guardados"
}

# Una copia al iniciar (por si el servidor estuvo apagado) y luego una al día a la hora indicada
run_backup || echo "[$(date)] ERROR en la copia inicial"
while true; do
  now=$(date +%s)
  next=$(date -d "$(date +%Y-%m-%d) $HOUR:00:00" +%s 2>/dev/null || echo $((now + 86400)))
  [ "$next" -le "$now" ] && next=$((next + 86400))
  sleep $((next - now))
  run_backup || echo "[$(date)] ERROR en la copia"
done
