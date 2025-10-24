import argparse
import json
from pathlib import Path
from typing import Any, Dict, Iterable, Optional, Sequence

from asteval import Interpreter


BASE_DIR = Path(__file__).resolve().parent


class TemplateRenderer:
    """Render structured payloads from template configuration files."""

    def __init__(
        self,
        config_path: Path,
        *,
        overrides: Optional[Dict[str, Any]] = None,
        table_ids: Optional[Iterable[str]] = None,
    ) -> None:
        self.config_path = config_path
        self.overrides = dict(overrides or {})
        self.table_ids = set(table_ids) if table_ids is not None else None
        self._config: Optional[Dict[str, Any]] = None
        self._values: Optional[Dict[str, Any]] = None

    # ── Core orchestration ──────────────────────────────────────────────
    def build_payload(self) -> Dict[str, Any]:
        config = self._load_config()
        values = self._compute_values(config.get("fields", []))
        layout = config.get("layout", {})

        return {
            "title": config.get("title"),
            "currency": config.get("currency"),
            "inputs": self._build_inputs(config, values),
            "tables": self._build_tables(layout, values),
            "notes": layout.get("notes") or config.get("notes", []),
        }

    def write_payload(self, destination: Path) -> Path:
        payload = self.build_payload()
        destination.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf8",
        )
        return destination

    # ── Helpers ────────────────────────────────────────────────────────
    def _load_config(self) -> Dict[str, Any]:
        if self._config is None:
            with open(self.config_path, "r", encoding="utf8") as handle:
                self._config = json.load(handle)
        return self._config

    def _compute_values(self, fields: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
        if self._values is not None:
            return self._values

        ctx: Dict[str, Any] = dict(self.overrides)

        for field in fields:
            if field.get("source", "user") == "user" and field["id"] not in ctx:
                ctx[field["id"]] = field.get("default")

        engine = Interpreter()
        for _ in range(8):
            changed = False
            engine.symtable.update(ctx)
            for field in fields:
                if field.get("source") == "calc" and "formula" in field:
                    result = engine(field["formula"])
                    if ctx.get(field["id"]) != result:
                        ctx[field["id"]] = result
                        changed = True
            if not changed:
                break

        self._values = ctx
        return ctx

    @staticmethod
    def _format_value(value: Any, fmt: Optional[str]) -> Any:
        if value is None or fmt is None:
            return value

        if fmt == "money":
            try:
                num = float(value)
            except (TypeError, ValueError):
                return value
            num = round(num, 2)
            if num.is_integer():
                return int(num)
            return num

        if fmt == "percent":
            try:
                num = float(value)
            except (TypeError, ValueError):
                return value
            return f"{num:.2f}%"

        if fmt == "percent_per_year":
            try:
                num = float(value)
            except (TypeError, ValueError):
                return value
            return f"{num:.2f}%/năm"

        if fmt == "integer":
            try:
                return int(value)
            except (TypeError, ValueError):
                return value

        return value

    def _resolve_extra_label(
        self, row_cfg: Dict[str, Any], values: Dict[str, Any]
    ) -> Optional[Any]:
        extra = row_cfg.get("extra_label")
        if extra is None:
            return None

        if isinstance(extra, dict):
            if "field" in extra:
                value = values.get(extra["field"])
                return self._format_value(value, extra.get("format"))
            return extra.get("text")

        return extra

    def _build_cell(
        self, cell_cfg: Dict[str, Any], values: Dict[str, Any]
    ) -> Dict[str, Any]:
        if "field" in cell_cfg:
            raw = values.get(cell_cfg["field"])
        else:
            raw = cell_cfg.get("value")

        formatted = self._format_value(raw, cell_cfg.get("format"))
        return {
            "value": formatted,
            "editable": cell_cfg.get("editable", False),
        }

    def _build_inputs(
        self, config: Dict[str, Any], values: Dict[str, Any]
    ) -> Dict[str, Any]:
        inputs: Dict[str, Any] = {}
        for item in config.get("inputs", []):
            key = item.get("key") or item.get("id")
            field_id = item.get("field") or item.get("id")
            value = values.get(field_id)
            inputs[key] = self._format_value(value, item.get("format"))
        return inputs

    def _build_tables(self, layout: Dict[str, Any], values: Dict[str, Any]) -> Any:
        tables = []
        for table_cfg in layout.get("tables", []):
            if self.table_ids is not None and table_cfg.get("id") not in self.table_ids:
                continue
            table = {
                "id": table_cfg["id"],
                "title": table_cfg.get("title", ""),
                "rows": [],
            }

            col_defs = list(table_cfg.get("col_defs", []))
            if col_defs:
                table["col_defs"] = col_defs

            for row_cfg in table_cfg.get("rows", []):
                table["rows"].append(self._build_row(row_cfg, values))

            if "note" in table_cfg:
                table["note"] = table_cfg["note"]

            tables.append(table)

        return tables

    def _build_row(self, row_cfg: Dict[str, Any], values: Dict[str, Any]) -> Dict[str, Any]:
        row = {
            "id": row_cfg["id"],
            "label": row_cfg.get("label", ""),
        }

        if "type" in row_cfg:
            row["type"] = row_cfg["type"]

        extra_label = self._resolve_extra_label(row_cfg, values)
        if extra_label is not None:
            row["extra_label"] = extra_label

        cells = {}
        for col_key, cell_cfg in row_cfg.get("cells", {}).items():
            cells[col_key] = self._build_cell(cell_cfg, values)
        row["cells"] = cells

        children_cfg = row_cfg.get("children")
        if children_cfg:
            row["children"] = [self._build_row(child_cfg, values) for child_cfg in children_cfg]

        return row


def _auto_cast(value: str) -> Any:
    """Try to cast CLI overrides to int/float/bool/json when possible."""
    lowered = value.lower()
    if lowered in {"true", "false"}:
        return lowered == "true"
    try:
        if "." in value:
            return float(value)
        return int(value)
    except ValueError:
        pass
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return value


def _parse_overrides(pairs: Sequence[str]) -> Dict[str, Any]:
    overrides: Dict[str, Any] = {}
    for item in pairs:
        if "=" not in item:
            raise ValueError(f"Override must be in key=value format (got {item!r})")
        key, raw_value = item.split("=", 1)
        overrides[key.strip()] = _auto_cast(raw_value.strip())
    return overrides


def _collect_configs(config_args: Sequence[str]) -> Sequence[Path]:
    if config_args:
        return [Path(arg).expanduser().resolve() for arg in config_args]
    return sorted((BASE_DIR / "config").glob("template_scenario*.json"))


def render_config(
    config_path: Path,
    *,
    output_dir: Path,
    overrides: Optional[Dict[str, Any]] = None,
    table_ids: Optional[Iterable[str]] = None,
) -> Path:
    renderer = TemplateRenderer(config_path, overrides=overrides, table_ids=table_ids)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{config_path.stem}_payload.json"
    renderer.write_payload(output_path)
    return output_path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Render structured payloads for one or many scenario templates."
    )
    parser.add_argument(
        "configs",
        nargs="*",
        help="Path(s) to template JSON configs. Defaults to template_scenario*.json.",
    )
    parser.add_argument(
        "--output-dir",
        default=BASE_DIR,
        help="Directory to write rendered payloads (default: repository render/ directory).",
    )
    parser.add_argument(
        "--table-id",
        dest="table_ids",
        action="append",
        default=None,
        help="Optional table id filter (can be specified multiple times).",
    )
    parser.add_argument(
        "--override",
        action="append",
        default=None,
        help="Override field values using key=value (can be repeated).",
    )

    args = parser.parse_args()

    try:
        override_map = _parse_overrides(args.override or [])
    except ValueError as exc:
        parser.error(str(exc))
        return

    configs = _collect_configs(args.configs)
    if not configs:
        parser.error("No template configuration files found.")
        return

    output_dir = Path(args.output_dir).expanduser().resolve()
    for config_path in configs:
        output_path = render_config(
            config_path,
            output_dir=output_dir,
            overrides=override_map if override_map else None,
            table_ids=args.table_ids,
        )
        try:
            display_path = output_path.relative_to(output_dir)
        except ValueError:
            display_path = output_path
        print(f"✅ Rendered {config_path.name} → {display_path}")


if __name__ == "__main__":
    main()
