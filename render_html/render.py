from dataclasses import dataclass
from pathlib import Path
import json
from typing import Any, Dict, Iterable, List, Optional

from asteval import Interpreter
from jinja2 import Environment, FileSystemLoader

DEFAULT_TITLE = "Bảng so sánh phương án tái tài trợ"


# ────────────────────────────────────────────────
# Scenario builder core
class ScenarioBuilder:
    """Encapsulates config loading, evaluation, and field preparation."""

    def __init__(
        self,
        globals_path: str | Path,
        scenario_path: str | Path,
        *,
        inputs: Optional[Dict[str, Any]] = None,
        units: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.globals_path = Path(globals_path)
        self.scenario_path = Path(scenario_path)
        self.inputs = dict(inputs or {})
        self.units = dict(units or {})

        self._globals_cfg: Optional[Dict[str, Any]] = None
        self._scenario_cfg: Optional[Dict[str, Any]] = None
        self._fields: Optional[List[Dict[str, Any]]] = None
        self._values: Optional[Dict[str, Any]] = None

    # Loading helpers -----------------------------------------------------
    @staticmethod
    def _load_json(path: Path) -> Dict[str, Any]:
        with open(path, "r", encoding="utf8") as handle:
            return json.load(handle)

    # Merge globals + scenario with overrides -----------------------------
    @staticmethod
    def _merge_fields(globals_cfg: Dict[str, Any], scenario_cfg: Dict[str, Any]) -> List[Dict[str, Any]]:
        gmap = {field["id"]: field for field in globals_cfg.get("fields", [])}
        merged: List[Dict[str, Any]] = []

        for field_id in scenario_cfg.get("use_fields", []):
            base = dict(gmap[field_id])
            overrides = scenario_cfg.get("overrides", {}).get(field_id, {})
            for key in ("unit", "default"):
                if key in overrides:
                    base[key] = overrides[key]
            base["source"] = "user"
            merged.append(base)

        merged.extend(scenario_cfg.get("fields", []))
        return merged

    # Evaluate formulas ---------------------------------------------------
    @staticmethod
    def _compute_values(fields: Iterable[Dict[str, Any]], inputs: Dict[str, Any]) -> Dict[str, Any]:
        ctx: Dict[str, Any] = dict(inputs)

        for field in fields:
            if field.get("source") == "user" and field["id"] not in ctx:
                ctx[field["id"]] = field.get("default")

        engine = Interpreter()
        for _ in range(8):
            changed = False
            engine.symtable.update(ctx)
            for field in fields:
                if field.get("source") == "calc" and "formula" in field:
                    value = engine(field["formula"])
                    if ctx.get(field["id"]) != value:
                        ctx[field["id"]] = value
                        changed = True
            if not changed:
                break

        return ctx

    # Field presentation helpers -----------------------------------------
    @staticmethod
    def _resolve_label(field: Dict[str, Any], globals_cfg: Dict[str, Any], scenario_cfg: Dict[str, Any]) -> str:
        if field.get("label"):
            return field["label"]
        labels = scenario_cfg.get("field_labels", {})
        if field["id"] in labels:
            return labels[field["id"]]
        gmap = {f["id"]: f for f in globals_cfg.get("fields", [])}
        if field["id"] in gmap and gmap[field["id"]].get("label"):
            return gmap[field["id"]]["label"]
        return field["id"].replace("_", " ").title()

    def _resolve_unit(self, field: Dict[str, Any]) -> Optional[str]:
        if field["id"] in self.units:
            return self.units[field["id"]]
        return field.get("unit")

    def _normalise_value(self, field: Dict[str, Any], value: Any, unit: Optional[str]) -> Any:
        return value

    # Public API ----------------------------------------------------------
    def build(self) -> "ScenarioData":
        globals_cfg = self._globals_cfg or self._load_json(self.globals_path)
        scenario_cfg = self._scenario_cfg or self._load_json(self.scenario_path)
        self._globals_cfg = globals_cfg
        self._scenario_cfg = scenario_cfg

        fields = self._fields or self._merge_fields(globals_cfg, scenario_cfg)
        values = self._values or self._compute_values(fields, self.inputs)
        self._fields = fields
        self._values = values

        prepared_fields: List[FieldOutput] = []
        for field in fields:
            unit = self._resolve_unit(field)
            label = self._resolve_label(field, globals_cfg, scenario_cfg)
            prepared_fields.append(
                FieldOutput(
                    id=field["id"],
                    label=label,
                    type=field.get("type"),
                    unit=unit,
                    source=field.get("source"),
                    value=self._normalise_value(field, values.get(field["id"]), unit),
                )
            )

        return ScenarioData(
            scenario_id=scenario_cfg.get("scenario_id"),
            title=scenario_cfg.get("title", DEFAULT_TITLE),
            choices=list(scenario_cfg.get("choices", [])),
            fields=prepared_fields,
            values=values,
        )


@dataclass
class FieldOutput:
    id: str
    label: Optional[str]
    type: Optional[str]
    unit: Optional[str]
    source: Optional[str]
    value: Any

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "label": self.label,
            "type": self.type,
            "unit": self.unit,
            "source": self.source,
            "value": self.value,
        }


@dataclass
class ScenarioData:
    scenario_id: Optional[str]
    title: str
    choices: List[Dict[str, Any]]
    fields: List[FieldOutput]
    values: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "scenario_id": self.scenario_id,
            "title": self.title,
            "choices": self.choices,
            "fields": [field.to_dict() for field in self.fields],
            "values": self.values,
        }


def prepare_scenario_data(
    globals_path: str | Path,
    scenario_path: str | Path,
    *,
    inputs: Optional[Dict[str, Any]] = None,
    units: Optional[Dict[str, Any]] = None,
) -> ScenarioData:
    builder = ScenarioBuilder(globals_path, scenario_path, inputs=inputs, units=units)
    return builder.build()


# ────────────────────────────────────────────────
# 4. render HTML (optional: can be skipped by downstream consumers)
def render_html(prepared: ScenarioData, templates_path: str | Path) -> str:
    env = Environment(loader=FileSystemLoader(templates_path))
    env.filters["money"] = lambda v: f"{v:,.0f}".replace(",", ".")
    env.filters["number"] = lambda v: f"{v:.2f}" if isinstance(v, (float, int)) else v

    rendered_blocks: List[str] = []
    for choice in prepared.choices:
        tpl = env.get_template(choice["template"])
        block = tpl.render(choice=choice, **prepared.values)
        rendered_blocks.append(block)

    wrapper = env.get_template("wrapper.html")
    return wrapper.render(
        scenario_id=prepared.scenario_id,
        title=prepared.title,
        rendered_choices=rendered_blocks,
    )


def write_rendered_html(html: str, *, destination: str | Path = "rendered_output.html") -> Path:
    destination_path = Path(destination)
    destination_path.write_text(html, encoding="utf8")
    return destination_path


# ────────────────────────────────────────────────
if __name__ == "__main__":
    data = prepare_scenario_data("config/globals.json", "config/scenario_refinance.json")
    print("✅ Data prepared →", data.to_dict())
    print("✅ Rendering HTML...")
    html_output = render_html(data, "templates")
    output_path = write_rendered_html(html_output)
    print(f"✅ Rendered → {output_path.resolve()}")
