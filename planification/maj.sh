#!/bin/sh
# Mise à jour planifiée : à lancer depuis cron, systemd ou launchd. Journal dans data/journaux/.
# Une seule exécution à la fois (verrou en base). Code de sortie non nul en cas d'échec.
set -eu
cd "$(dirname "$0")/.."
PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:$PATH"
export PATH NO_COLOR=1 COLUMNS=160
journaux="${VI_DATA_DIR:-data}/journaux"
mkdir -p "$journaux"
find "$journaux" -name 'maj-*.txt' -mtime +180 -delete
exec uv run --frozen vi maj "$@" >>"$journaux/maj-$(date +%Y-%m-%d).txt" 2>&1
