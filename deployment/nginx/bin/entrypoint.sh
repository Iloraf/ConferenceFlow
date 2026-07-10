#!/bin/sh

: "${DOMAIN:?DOMAIN is not set or is empty}"
: "${EMAIL:?EMAIL is not set or is empty}"

# use envsubst to fill placeholders in the Nginx app config file
if [ -f /etc/nginx/conf.d/app.conf ]; then
    envsubst </etc/nginx/conf.d/app.conf >/etc/nginx/conf.d/app.subst.conf &&
      rm /etc/nginx/conf.d/app.conf
fi

# Chemins acme.sh
ACME_SH="/root/.acme.sh/acme.sh"
CERT_DIR="/etc/letsencrypt/live/${DOMAIN}"
mkdir -p "${CERT_DIR}"

# Configurer acme.sh avec l'email
${ACME_SH} --register-account -m "${EMAIL}" --server letsencrypt || true

# Obtenir le certificat AVANT de démarrer nginx (port 443 libre)
${ACME_SH} --issue -d "${DOMAIN}" --alpn --standalone --tlsport 5443 --server letsencrypt || true

# Installer les certificats avec hook de rechargement automatique
${ACME_SH} --install-cert -d "${DOMAIN}" \
    --cert-file "${CERT_DIR}/cert.pem" \
    --key-file "${CERT_DIR}/privkey.pem" \
    --fullchain-file "${CERT_DIR}/fullchain.pem" \
    --ca-file "${CERT_DIR}/chain.pem" \
    --reloadcmd "/usr/sbin/nginx -s reload" || true

# Démarrer nginx et cron
/usr/sbin/crond && /usr/sbin/nginx -g "daemon off;"
