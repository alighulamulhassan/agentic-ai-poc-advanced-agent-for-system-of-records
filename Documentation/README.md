# Documentation

| File | What it is |
| --- | --- |
| [ARCHITECTURE.md](ARCHITECTURE.md) | System architecture overview |
| [BUSINESS_CASE.md](BUSINESS_CASE.md) | Business rationale for the workshop |
| [GOVERNANCE_PLAYBOOK.md](GOVERNANCE_PLAYBOOK.md) | Governance patterns for production agents |
| [AUDIENCE_FAQ.md](AUDIENCE_FAQ.md) | Anticipated workshop Q&A |
| [WORKSHOP_DECK.md](WORKSHOP_DECK.md) | Marpit slide deck for the workshop |
| [diagrams/](diagrams/) | Mermaid sources and rendered SVGs used by the deck |
| [marp-themes/tall.css](marp-themes/tall.css) | Custom 1280×960 Marpit theme used by the deck |

---

## Exporting the deck to PowerPoint

The deck source is [WORKSHOP_DECK.md](WORKSHOP_DECK.md) (Marpit). Diagrams live as Mermaid sources in [diagrams/](diagrams/) and are rendered to SVG before export.

### One-shot export

```bash
cd Documentation
./export-deck.sh
```

This will:
1. Re-render every `*.mmd` in `diagrams/` to SVG via `mmdc`
2. Convert `WORKSHOP_DECK.md` to `WORKSHOP_DECK.pptx` via `marp-cli`, registering the custom theme so the canvas matches the VS Code preview (1280×960)

The output lands at `Documentation/WORKSHOP_DECK.pptx` and is fully self-contained — image SVGs are embedded; no external paths.

### Skip diagram regeneration (faster)

If only the deck text changed and diagram sources are untouched:

```bash
./export-deck.sh --skip-diagrams
```

### What gets installed on first run

Both `mmdc` (Mermaid CLI) and `marp-cli` use Puppeteer, which downloads a Chromium binary (~300 MB) the first time it runs. Subsequent runs use the cached browser. The download is one-time and lives under your user's npm/puppeteer cache, not the repo.

### Editing the deck

- **Text changes:** edit [WORKSHOP_DECK.md](WORKSHOP_DECK.md) directly. The Marp for VS Code extension shows a live preview when you open it. The custom theme is registered via `.vscode/settings.json`; reload the window once after first checkout (`Cmd+Shift+P → Developer: Reload Window`).
- **Diagram changes:** edit the relevant `*.mmd` file in [diagrams/](diagrams/), then either run `./diagrams/regenerate.sh` or just `./export-deck.sh` (which calls regenerate first).
- **Theme changes:** edit [marp-themes/tall.css](marp-themes/tall.css). Both VS Code preview and `export-deck.sh` use the same file.

### Other output formats

`export-deck.sh` produces PPTX. For PDF or PNG-per-slide, swap the `--pptx` flag inside the script:

```bash
# in export-deck.sh, change:
--pptx
# to one of:
--pdf
--images png
```
