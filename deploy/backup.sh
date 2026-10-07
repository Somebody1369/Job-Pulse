#!/bin/sh
# Dumps the database into backups/ and keeps the newest BACKUP_KEEP dumps (14 by default).
set -eu
cd "$(dirname "$0")/.."

keep="${BACKUP_KEEP:-14}"
file="backups/jobpulse-$(date +%Y%m%d-%H%M%S).dump"

mkdir -p backups
docker compose exec -T db sh -c 'pg_dump --format custom --username "$POSTGRES_USER" "$POSTGRES_DB"' \
    > "$file.partial"
mv "$file.partial" "$file"

ls -1t backups/jobpulse-*.dump | tail -n +"$((keep + 1))" | while read -r old; do
    rm -- "$old"
done
echo "Saved $file"
