#!/bin/sh
set -e

# Corrige les permissions des dossiers montes en volume (uploads, content)
# avant de basculer sur l'utilisateur non-root pour l'execution reelle.
mkdir -p app/static/uploads app/static/content
chown -R appuser:appuser app/static/uploads app/static/content

exec gosu appuser "$@"
