#!/bin/sh
set -eu

: "${AIRCO_PUBLIC_DOMAIN:?AIRCO_PUBLIC_DOMAIN is required}"
: "${AIRCO_SSL_CERT_PATH:?AIRCO_SSL_CERT_PATH is required}"
: "${AIRCO_SSL_KEY_PATH:?AIRCO_SSL_KEY_PATH is required}"

export AIRCO_PUBLIC_DOMAIN AIRCO_SSL_CERT_PATH AIRCO_SSL_KEY_PATH

envsubst '${AIRCO_PUBLIC_DOMAIN} ${AIRCO_SSL_CERT_PATH} ${AIRCO_SSL_KEY_PATH}' \
  < /etc/nginx/nginx.ec2.conf.template \
  > /etc/nginx/nginx.conf

exec nginx -g 'daemon off;'
