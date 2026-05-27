"""Load a region YAML and expose it as dotted-access objects."""
from __future__ import annotations

import os
from pathlib import Path
from types import SimpleNamespace
from typing import Any

try:
    import yaml
except ImportError as exc:
    raise SystemExit(
        "PyYAML is required. From ArcGIS Pro's Python prompt run: "
        "pip install pyyaml"
    ) from exc


def _ns(obj: Any) -> Any:
    """Recursively convert dict/list trees to SimpleNamespace + lists.

    Keeps int keys (e.g. the palette {1: {...}}) as dicts since attribute
    access doesn't work for integer keys.
    """
    if isinstance(obj, dict):
        has_int_keys = any(isinstance(k, int) for k in obj.keys())
        if has_int_keys:
            return {k: _ns(v) for k, v in obj.items()}
        return SimpleNamespace(**{k: _ns(v) for k, v in obj.items()})
    if isinstance(obj, list):
        return [_ns(v) for v in obj]
    return obj


def load(path: str | os.PathLike) -> SimpleNamespace:
    """Load a YAML config and return it as a nested SimpleNamespace.

    Also normalizes path strings to absolute, creates a `cfg.config_path`
    field, and exposes the raw dict at `cfg._raw` for tools that need it.
    """
    path = Path(path).resolve()
    with path.open("r", encoding="utf-8") as fh:
        raw = yaml.safe_load(fh)

    cfg = _ns(raw)
    cfg.config_path = str(path)
    cfg._raw = raw
    return cfg


def ensure_dirs(cfg: SimpleNamespace) -> None:
    """Create the on-disk folder structure the pipeline writes to."""
    for key in ("inputs_gee", "inputs_esri_s2", "inputs_vector",
                "derivatives", "outputs", "logs"):
        Path(getattr(cfg.paths, key)).mkdir(parents=True, exist_ok=True)
