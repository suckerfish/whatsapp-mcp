#!/bin/sh
TOKEN=$(cat /app/store/.bridge-token 2>/dev/null | tr -d '\n')
wget -qO- --header="Authorization: Bearer $TOKEN" http://localhost:8080/api/health | grep -q '"connected":true' || exit 1
if [ -n "$HEALTHCHECKS_PING_URL" ]; then
    wget -qO- "$HEALTHCHECKS_PING_URL" > /dev/null
fi
