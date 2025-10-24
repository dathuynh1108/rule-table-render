import argparse
import html
import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence

from render import TemplateRenderer, _parse_overrides


DEFAULT_OUTPUT = Path("render_json_demo.html")
BASE_DIR = Path(__file__).resolve().parent


def _ensure_sequence(value: Optional[Iterable[str]]) -> Optional[Sequence[str]]:
    if value is None:
        return None
    if isinstance(value, Sequence):
        return value
    return list(value)


def _load_payload(
    config_path: Path,
    overrides: Optional[Dict[str, Any]] = None,
    table_ids: Optional[Iterable[str]] = None,
) -> Dict[str, Any]:
    renderer = TemplateRenderer(
        config_path,
        overrides=overrides,
        table_ids=_ensure_sequence(table_ids),
    )
    return renderer.build_payload()


def _render_inputs(inputs: Dict[str, Any]) -> str:
    if not inputs:
        return ""

    rows = []
    for key, value in inputs.items():
        rows.append(
            f"<tr><th>{html.escape(str(key))}</th><td>{html.escape(str(value))}</td></tr>"
        )

    return (
        "<section class='inputs'>"
        "<h2>Thông số đầu vào</h2>"
        "<table class='simple-table'>"
        "<tbody>"
        f"{''.join(rows)}"
        "</tbody>"
        "</table>"
        "</section>"
    )


def _render_data_snapshot(data: Dict[str, Dict[str, Any]]) -> str:
    if not data:
        return ""

    rows = []
    for field_id, meta in data.items():
        value = meta.get("value")
        source = meta.get("source", "user")
        type_ = meta.get("type") or ""
        attrs: List[str] = []
        if source:
            attrs.append(f"source: {source}")
        if type_:
            attrs.append(f"type: {type_}")
        if "formula" in meta:
            attrs.append(f"formula: {meta['formula']}")
        if "default" in meta and meta["default"] != value:
            attrs.append(f"default: {meta['default']}")
        meta_text = ", ".join(attrs)

        rows.append(
            "<tr>"
            f"<th>{html.escape(field_id)}</th>"
            f"<td>{html.escape(json.dumps(value, ensure_ascii=False))}</td>"
            f"<td>{html.escape(meta_text)}</td>"
            "</tr>"
        )

    return (
        "<details class='data-dump'>"
        "<summary>Dữ liệu thô</summary>"
        "<table class='data-table'>"
        "<thead><tr><th>Field</th><th>Value</th><th>Meta</th></tr></thead>"
        "<tbody>"
        f"{''.join(rows)}"
        "</tbody>"
        "</table>"
        "</details>"
    )


def _render_table(table: Dict[str, Any]) -> str:
    col_defs = table.get("col_defs")
    has_multiple_cols = bool(col_defs)
    headers_html = _render_table_headers(col_defs)
    body_rows = "".join(
        _render_row(row, col_defs, depth=0) for row in table.get("rows", [])
    )
    note_html = ""
    if table.get("note"):
        note_html = f"<div class='table-note'>{html.escape(table['note'])}</div>"

    return (
        "<section class='table-block'>"
        f"<h2>{html.escape(table.get('title', ''))}</h2>"
        "<table class='data-table'>"
        f"{headers_html}"
        f"<tbody>{body_rows}</tbody>"
        "</table>"
        f"{note_html}"
        "</section>"
    )


def _render_table_headers(col_defs: Optional[Sequence[Dict[str, Any]]]) -> str:
    if not col_defs:
        return "<thead><tr><th class='col-label'>Hạng mục</th><th>Giá trị</th></tr></thead>"

    header_cells = ["<th class='col-label'>Hạng mục</th>"]
    for col in col_defs:
        title = html.escape(col.get("title", ""))
        subtitle = col.get("subtitle")
        if subtitle:
            subtitle_html = f"<div class='subtitle'>{html.escape(subtitle)}</div>"
        else:
            subtitle_html = ""
        header_cells.append(f"<th><div>{title}{subtitle_html}</div></th>")

    return f"<thead><tr>{''.join(header_cells)}</tr></thead>"


def _render_row(
    row: Dict[str, Any],
    col_defs: Optional[Sequence[Dict[str, Any]]],
    *,
    depth: int,
) -> str:
    row_type = row.get("type")
    classes = ["row"]
    if row_type == "label":
        classes.append("row-label")
    if row_type == "total":
        classes.append("row-total")

    indent_px = depth * 18
    label_parts = [html.escape(row.get("label", ""))]
    if row.get("extra_label") is not None:
        label_parts.append(
            f"<span class='extra-label'>{html.escape(str(row['extra_label']))}</span>"
        )
    label_html = " ".join(label_parts)

    cells_html = []
    if col_defs:
        for col in col_defs:
            cell_cfg = row.get("cells", {}).get(col.get("key", ""), {})
            cells_html.append(_render_cell(cell_cfg))
    else:
        cell_cfg = row.get("cells", {}).get("main", {})
        cells_html.append(_render_cell(cell_cfg))

    row_html = (
        f"<tr class=\"{' '.join(classes)}\">"
        f"<th style='padding-left:{indent_px}px'>{label_html}</th>"
        f"{''.join(cells_html)}"
        "</tr>"
    )

    children_html = ""
    for child in row.get("children", []):
        children_html += _render_row(child, col_defs, depth=depth + 1)

    return row_html + children_html


def _render_cell(cell_cfg: Dict[str, Any]) -> str:
    value = cell_cfg.get("value")
    if value is None:
        display = ""
    else:
        display = html.escape(str(value))

    classes = ["value-cell"]
    if not cell_cfg.get("editable", False):
        classes.append("readonly")
    return f"<td class=\"{' '.join(classes)}\">{display}</td>"


def _render_notes(notes: Sequence[str]) -> str:
    if not notes:
        return ""

    items = "".join(f"<li>{html.escape(note)}</li>" for note in notes)
    return f"<section class='notes'><h2>Ghi chú</h2><ul>{items}</ul></section>"


def _render_payload(payload: Dict[str, Any]) -> str:
    sections = [
        f"<header><h1>{html.escape(payload.get('title', ''))}</h1>"
        f"<div class='currency'>Đơn vị: {html.escape(payload.get('currency', ''))}</div>"
        "</header>"
    ]

    sections.append(_render_inputs(payload.get("inputs", {})))
    sections.append(_render_data_snapshot(payload.get("data", {})))

    for table in payload.get("tables", []):
        sections.append(_render_table(table))

    sections.append(_render_notes(payload.get("notes", [])))
    return "".join(filter(None, sections))


def _wrap_document(body: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="vi">
<head>
  <meta charset="utf-8" />
  <title>Demo Render JSON</title>
  <style>
    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      margin: 2rem;
      background: #f6f8fa;
      color: #1f2933;
    }}
    header {{
      margin-bottom: 2rem;
    }}
    header h1 {{
      margin: 0;
      font-size: 2rem;
      color: #0f4c82;
    }}
    header .currency {{
      margin-top: 0.25rem;
      color: #52606d;
      font-size: 0.95rem;
    }}
    section {{
      background: #fff;
      border-radius: 12px;
      padding: 1.5rem;
      margin-bottom: 1.5rem;
      box-shadow: 0 2px 4px rgba(15, 76, 130, 0.08);
    }}
    section h2 {{
      margin-top: 0;
      color: #0f4c82;
      font-size: 1.25rem;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
    }}
    th, td {{
      padding: 0.55rem 0.75rem;
      border-bottom: 1px solid #e4eff8;
      text-align: left;
      vertical-align: top;
    }}
    th.col-label {{
      width: 35%;
    }}
    .row-label th {{
      background: #f0f6fc;
      font-weight: 600;
    }}
    .row-total {{
      font-weight: 700;
      background: #e1f6ff;
    }}
    .value-cell.readonly {{
      color: #425466;
    }}
    .extra-label {{
      display: inline-block;
      margin-left: 0.35rem;
      padding: 0.1rem 0.4rem;
      border-radius: 999px;
      background: #e1f6ff;
      color: #0f4c82;
      font-size: 0.8rem;
    }}
    .subtitle {{
      display: block;
      font-size: 0.8rem;
      color: #52606d;
      margin-top: 0.15rem;
    }}
    .table-note {{
      margin-top: 0.5rem;
      font-style: italic;
      color: #52606d;
    }}
    .notes ul {{
      margin: 0;
      padding-left: 1.25rem;
    }}
    .notes li {{
      margin-bottom: 0.5rem;
    }}
    details.data-dump {{
      margin-top: 1rem;
    }}
    details.data-dump summary {{
      cursor: pointer;
      font-weight: 600;
    }}
    .inputs table th {{
      width: 40%;
      color: #0f4c82;
    }}
  </style>
</head>
<body>
{body}
</body>
</html>
"""


def render_configs_to_html(
    config_paths: Sequence[Path],
    *,
    overrides: Optional[Dict[str, Any]] = None,
    table_ids: Optional[Iterable[str]] = None,
) -> str:
    sections = []
    for path in config_paths:
        payload = _load_payload(path, overrides=overrides, table_ids=table_ids)
        sections.append(_render_payload(payload))
    body = "".join(sections)
    return _wrap_document(body)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Render scenario JSON configs to an HTML preview."
    )
    parser.add_argument(
        "configs",
        nargs="*",
        default=None,
        help="Path(s) to template config JSON files. Defaults to template_scenario*.json.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"Destination HTML file (default: {DEFAULT_OUTPUT.name}).",
    )
    parser.add_argument(
        "--override",
        action="append",
        default=[],
        metavar="KEY=VALUE",
        help="Override field values. Can be provided multiple times.",
    )
    parser.add_argument(
        "--table-id",
        dest="table_ids",
        action="append",
        help="Render only the specified table id (may be used multiple times).",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()

    if args.configs:
        config_paths = [Path(path).expanduser().resolve() for path in args.configs]
    else:
        config_paths = sorted(BASE_DIR.glob("config/template_scenario*.json"))

    overrides = _parse_overrides(args.override) if args.override else None

    html_output = render_configs_to_html(
        config_paths, overrides=overrides, table_ids=args.table_ids
    )
    args.output.write_text(html_output, encoding="utf8")
    print(f"✅ Rendered HTML → {args.output.resolve()}")


if __name__ == "__main__":
    main()
