#!/bin/bash
# fix_fonts.sh - Corrige les polices d'un article et crée une nouvelle version
# Usage: ./fix_fonts.sh <comm_id>

COMM_ID=$1
ARTICLES_DIR="data/uploads/articles"

if [ -z "$COMM_ID" ]; then
    echo "Usage: ./fix_fonts.sh <comm_id>"
    exit 1
fi

# Trouver la dernière version
LAST_FILE=$(ls -1 ${ARTICLES_DIR}/ar-${COMM_ID}-*.pdf 2>/dev/null | sort -t- -k3 -n | tail -1)

if [ -z "$LAST_FILE" ]; then
    echo "Aucun fichier trouvé pour la comm ${COMM_ID}"
    exit 1
fi

# Extraire le numéro de version
LAST_VERSION=$(echo "$LAST_FILE" | grep -oP '(?<=-)\d+(?=\.pdf)')
NEW_VERSION=$((LAST_VERSION + 1))
NEW_FILE="${ARTICLES_DIR}/ar-${COMM_ID}-${NEW_VERSION}.pdf"

echo "Dernière version: $LAST_FILE (v${LAST_VERSION})"
echo "Nouvelle version: $NEW_FILE (v${NEW_VERSION})"

# Appliquer gs pour re-embedder les polices
gs -dNOPAUSE -dBATCH -sDEVICE=pdfwrite -sOutputFile="$NEW_FILE" -dPDFSETTINGS=/prepress -dEmbedAllFonts=true -dSubsetFonts=true "$LAST_FILE"

if [ $? -ne 0 ]; then
    echo "Erreur ghostscript"
    exit 1
fi

# Corriger les permissions
chown systemd-coredump:systemd-coredump "$NEW_FILE"

# Insérer en base
FILESIZE=$(stat -c%s "$NEW_FILE")
docker exec -it conferenceflow-db-1 psql -U conference_user -d conference_flow -c "
INSERT INTO submission_file (communication_id, filename, original_filename, file_type, file_size, file_path, upload_date, version)
VALUES (${COMM_ID}, 'ar-${COMM_ID}-${NEW_VERSION}.pdf', 'ar-${COMM_ID}-${NEW_VERSION}.pdf', 'article', ${FILESIZE}, '/home/appuser/app/static/uploads/articles/ar-${COMM_ID}-${NEW_VERSION}.pdf', NOW(), ${NEW_VERSION});
"

# Supprimer le cache N&B
docker exec -it cflow_app rm -f /home/appuser/app/static/uploads/communications_gray/ar-${COMM_ID}-*.pdf

echo "Done: ar-${COMM_ID}-${NEW_VERSION}.pdf créé et enregistré en base"
