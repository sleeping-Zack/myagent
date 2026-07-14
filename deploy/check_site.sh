#!/bin/sh
set -eu

SITE_URL=${SITE_URL:-https://app8095.acapp.acwing.com.cn}
curl --fail --silent --show-error --max-time 10 "$SITE_URL/health/ready" > /dev/null
echo "site_ready=$SITE_URL"
