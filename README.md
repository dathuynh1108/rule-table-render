# rule-table-render

Tooling for turning financial scenario templates into machine-readable payloads and human-friendly HTML previews. The repository currently hosts two complementary pipelines:

- `render_json` – evaluate JSON template configs, calculate derived fields, and emit normalized payloads that downstream apps can consume.
- `render_html` – compose those calculated values into Jinja-based HTML snippets that can be embedded in slides, emails, or web views.

## Quick Start

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

Both pipelines only rely on `jinja2` (HTML rendering) and `asteval` (lightweight expression evaluator).

## Repository Layout

- `render_json/` – CLI + helpers for producing structured payloads from template configs under `render_json/config/`.
- `render_html/` – Scenario builder that merges global definitions with scenario-specific overrides and renders Jinja templates in `render_html/templates/`.
- `requirements.txt` – shared dependencies for both toolchains.

## JSON Payload Renderer (`render_json`)

### Template anatomy

Each config in `render_json/config/` declares:

- `fields`: list of user-provided or formula-driven values. Calculated fields (`source: "calc"`) use `formula` strings evaluated by `asteval`.
- `layout`: table definitions (titles, column definitions, rows, nested children, and notes) used to shape the rendered payload.
- Global metadata such as `title`, `currency`, and optional `notes`.

See `render_json/config/template_scenario1_refinance.json` for a complete example.

### CLI usage

Render every matching template with defaults:

```bash
python render_json/render.py
```

Render a single file, store results elsewhere, and override a few inputs:

```bash
python render_json/render.py render_json/config/template_scenario2_ttqt.json \
  --output-dir /tmp/payloads \
  --override loan_amount=3500000000 \
  --override penalty_pct=1.8 \
  --table-id loan_summary
```

Key flags:

- `configs`: optional list of template paths (defaults to `template_scenario*.json`).
- `--output-dir`: where the `*_payload.json` files are written (default: `render_json/`).
- `--override KEY=VALUE`: override any field (values are auto-cast to int/float/bool/JSON when possible).
- `--table-id`: limit output to specific table ids (repeatable).

### HTML preview for JSON payloads

`render_json/render_to_html.py` lets you inspect payloads visually without wiring them into the final product:

```bash
python render_json/render_to_html.py \
  render_json/config/template_scenario1_refinance.json \
  --output render_json_demo.html \
  --override loan_term_months=60
```

This script reuses the same renderer, then wraps the payload inside a minimal HTML UI that displays inputs, calculated data, and every rendered table.

## HTML Scenario Renderer (`render_html`)

The HTML pipeline is useful when you want to render directly from configs instead of consuming the JSON payloads.

Workflow:

1. **Prepare scenario data** – `ScenarioBuilder` merges global defaults (`render_html/config/globals.json`) with a scenario (`render_html/config/scenario_refinance.json`), applies overrides, evaluates formulas, and normalizes labels/units.
2. **Render Jinja templates** – `render_html/render.py` feeds the prepared values into templates under `render_html/templates/` (`acb.html`, `existing.html`, `wrapper.html`).
3. **Write the final artifact** – `write_rendered_html` persists the assembled markup (default `render_html/rendered_output.html`).

Example:

```bash
python render_html/render.py
```

That script prints the prepared data structure and writes the HTML comparison sheet defined in `templates/wrapper.html`.

## Development Notes

- Use Python ≥3.10 for best compatibility (repo is tested with 3.13 locally).
- Keep template configs small and composable; prefer calculated fields over repeated formulas in layouts.
- When adding new fields, remember to register user-input defaults and labels to keep both JSON payloads and HTML views in sync.

Happy rendering!
