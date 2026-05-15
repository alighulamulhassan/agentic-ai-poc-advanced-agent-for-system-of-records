#!/usr/bin/env bash
# Export WORKSHOP_DECK.md to PowerPoint (.pptx) via Marp CLI.
#
# Usage:
#   ./export-deck.sh                 # regenerate diagrams, then export
#   ./export-deck.sh --skip-diagrams # skip Mermaid re-render (faster)
#
# First run downloads Chromium via puppeteer (~300 MB, one-time).
# The custom theme (marp-themes/tall.css) is registered so 1280x960
# canvas + colors match the VS Code preview.

set -euo pipefail
cd "$(dirname "$0")"

INPUT="WORKSHOP_DECK.md"
OUTPUT="WORKSHOP_DECK.pptx"
THEME="./marp-themes/tall.css"

if [[ "${1:-}" != "--skip-diagrams" ]]; then
  echo "→ regenerating diagrams"
  ./diagrams/regenerate.sh
fi

echo "→ exporting $INPUT → $OUTPUT"
npx --yes -p @marp-team/marp-cli@latest marp \
  "$INPUT" \
  --pptx \
  --theme-set "$THEME" \
  --allow-local-files \
  --html \
  -o "$OUTPUT"

echo "done. $(pwd)/$OUTPUT"
