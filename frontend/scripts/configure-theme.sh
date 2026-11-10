#!/bin/sh
set -eu
attempt=0
until /opt/keycloak/bin/kcadm.sh config credentials --server http://keycloak:8080 --realm master --user "$THEME_ADMIN" --password "$THEME_PASSWORD" >/dev/null 2>&1; do
  attempt=$((attempt + 1))
  if [ "$attempt" -ge 60 ]; then
    echo "Keycloak theme setup failed: check realm admin credentials." >&2
    exit 1
  fi
  sleep 2
done
/opt/keycloak/bin/kcadm.sh update realms/vibedebate -s loginTheme=copper -s internationalizationEnabled=true -s 'supportedLocales=["ru","en"]' -s defaultLocale=ru
echo "VibeDebate login theme configured."
