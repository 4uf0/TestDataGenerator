#!/usr/bin/env bash
# Legt eine virtuelle Python-Umgebung an und installiert alle Abhängigkeiten.
# Verwendung: ./setup.sh  (danach: source .venv/bin/activate)

set -euo pipefail

cd "$(dirname "$0")"

VENV_DIR="${VENV_DIR:-.venv}"

if ! command -v python3 >/dev/null 2>&1; then
    echo "Fehler: python3 nicht gefunden. Bitte Python 3.10+ installieren." >&2
    exit 1
fi

echo "Erstelle virtuelle Umgebung in ${VENV_DIR} ..."
python3 -m venv "${VENV_DIR}"

# shellcheck disable=SC1091
source "${VENV_DIR}/bin/activate"

echo "Installiere Abhängigkeiten ..."
pip install --upgrade pip
pip install -r requirements.txt

echo
echo "Fertig. Umgebung aktivieren mit:"
echo "    source ${VENV_DIR}/bin/activate"
echo
echo "Dann z. B.:"
echo "    python generate_fit.py --duration 40"
echo "    GARMIN_EMAIL=... GARMIN_PASSWORD=... python upload_to_garmin.py out/"
