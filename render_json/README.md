# render_json

Opinionated toolkit for turning financial JSON templates into normalized payloads (and optional HTML previews) that downstream apps can plug into dashboards, PDFs, or APIs.

## Features

- Deterministic evaluation of user inputs + calculated fields via `asteval`.
- Layout-aware table builder (supports column definitions, nested rows, notes, editable flags).
- Easy CLI for rendering one or many templates, overriding inputs, and filtering specific tables.
- Optional HTML previewer so you can eyeball payloads without integrating them.

## Install

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r ../requirements.txt
```

All scripts only depend on `asteval` and the standard library.

## Directory Layout

- `config/` – Scenario templates (`template_scenario*.json`). Each file bundles metadata, field definitions, and layout instructions.
- `render.py` – Main CLI entry point (renders payloads to JSON).
- `render_to_html.py` – Convenience CLI that renders the same payload into a standalone HTML demo (`render_json_demo.html` by default).
- `*_payload.json` – Example outputs produced from the stock templates.

## Template Anatomy

Every template file follows this schema (see `config/template_scenario1_refinance.json`):

```jsonc
{
  "title": "Refinance Scenario",
  "currency": "VND",
  "notes": ["1. Lãi suất có thể thay đổi"],
  "fields": [
    { "id": "loan_amount", "source": "user", "type": "money", "default": 2_000_000_000 },
    { "id": "loan_term_years", "source": "calc", "formula": "loan_term_months / 12" }
  ],
  "layout": {
    "tables": [
      {
        "id": "loan_summary",
        "title": "Tổng quan",
        "col_defs": [{ "key": "main", "title": "Giá trị" }],
        "rows": [
          {
            "id": "loan_amount_row",
            "label": "Số tiền vay",
            "cells": { "main": { "field": "loan_amount", "format": "money" } }
          }
        ]
      }
    ],
    "notes": ["2. Giá trị làm tròn 2 chữ số thập phân"]
  }
}
```

Key ideas:

- **Fields**: Each field has an `id` and optionally `source` (`user` or `calc`), `default`, `formula`, `type`, and `editable` flag. Calculated fields can reference other fields by id.
- **Layout tables**: `tables` contain `rows`, and rows can include nested `children`. Cells either reference a `field` (auto-formatted) or a literal `value`. Column definitions (`col_defs`) let you render multi-column tables with custom headers/subtitles.
- **Notes**: Layout-level `notes` override top-level `notes` when present.

## CLI: `render.py`

Render all default templates (matching `config/template_scenario*.json`) and drop payloads next to the config files:

```bash
python render_json/render.py
```

Render a specific config, override inputs, and export payloads to a separate directory:

```bash
python render_json/render.py config/template_scenario2_ttqt.json \
  --output-dir /tmp/payloads \
  --override loan_amount=3500000000 \
  --override penalty_pct=1.8 \
  --table-id loan_summary \
  --table-id cash_flow
```

Supported flags:

- `configs`: optional list of template paths. Defaults to `template_scenario*.json`.
- `--output-dir`: destination directory for generated `*_payload.json`. Defaults to `render_json/`.
- `--override KEY=VALUE`: override user fields. Values are auto-cast (int/float/bool/JSON) when possible.
- `--table-id`: render only the tables with the given ids. Repeatable.

## HTML Preview: `render_to_html.py`

Need to inspect the payload visually? Generate a styled HTML snapshot:

```bash
python render_json/render_to_html.py \
  config/template_scenario1_refinance.json \
  --output render_json_demo.html \
  --override loan_term_months=60
```

This script reuses `TemplateRenderer`, then wraps the payload in a minimal UI that shows inputs, computed data, tables, and notes. Multiple configs can be supplied to stack sections in one document.

## Extending Templates

1. **Add fields**: Introduce new user or calculated fields in the `fields` array. Provide sensible `default` values so payloads render even without overrides.
2. **Reference fields in layout**: Use `cells.{col_key}.field` to bind a layout cell to a field. Apply built-in formats (`money`, `percent`, `percent_per_year`, `integer`) via `cells.{col_key}.format`.
3. **Guard formats**: If a calc might produce `None`, either set a fallback default or mark the cell `editable: false` so consumers know it is read-only.
4. **Test**: Run `python render_json/render.py <your_template>` and inspect the generated payload. For visual QA, run `render_to_html.py`.

## Tips

- The renderer performs up to 8 passes over calculated fields, so circular references will eventually stop updating but still leave inconsistent values—avoid them.
- `--override` accepts JSON, so arrays or nested structures can be injected with `--override config='{"key": "value"}'`.
- Commit example payloads (`*_payload.json`) for regression tracking when adding templates or formats.

Happy rendering!
