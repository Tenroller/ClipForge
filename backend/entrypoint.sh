#!/bin/sh
set -e

# Fix ownership of volume mount points (they may be root-owned from prior deploys)
chown -R appuser:appgroup /app/output /app/temp /app/logs /app/cache 2>/dev/null || true

# Drop privileges and exec the main process
exec su -s /bin/sh appuser -c "exec $*"
