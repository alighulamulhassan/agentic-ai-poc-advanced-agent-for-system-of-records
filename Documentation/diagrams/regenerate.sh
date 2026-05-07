#!/usr/bin/env bash
# Re-render every Mermaid source (.mmd) in this directory to SVG.
# First run downloads Chromium via puppeteer (~300 MB, one-time).
set -euo pipefail
cd "$(dirname "$0")"
for src in *.mmd; do
  out="${src%.mmd}.svg"
  echo "→ $src → $out"
  npx --yes -p @mermaid-js/mermaid-cli@latest mmdc -i "$src" -o "$out" -b transparent --quiet
done
echo "done."
