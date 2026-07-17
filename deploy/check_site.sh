#!/bin/sh
set -eu

SITE_URL=${SITE_URL:-https://yaoanxin.xyz}
curl --fail --silent --show-error --max-time 10 "$SITE_URL/health/ready" > /dev/null
echo "site_ready=$SITE_URL"
