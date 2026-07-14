#!/bin/sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
PROJECT_DIR=$(dirname "$SCRIPT_DIR")
BACKUP_DIR="$PROJECT_DIR/backups/postgres"
TIMESTAMP=$(date -u +%Y%m%dT%H%M%SZ)

mkdir -p "$BACKUP_DIR"
cd "$PROJECT_DIR"
docker compose exec -T postgres pg_dump -U personal_agent -d personal_agent -Fc > "$BACKUP_DIR/personal_agent_$TIMESTAMP.dump"
find "$BACKUP_DIR" -type f -name 'personal_agent_*.dump' -mtime +7 -delete

echo "backup_created=$BACKUP_DIR/personal_agent_$TIMESTAMP.dump"
