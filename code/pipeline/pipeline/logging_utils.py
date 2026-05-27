"""Console + file logging shared across phases."""
from __future__ import annotations

import logging
import sys
from datetime import datetime
from pathlib import Path


def setup_logging(log_dir: str, phase_label: str) -> Path:
    """Configure root logger to write to console + a per-run log file."""
    Path(log_dir).mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = Path(log_dir) / f"{stamp}_{phase_label}.log"

    root = logging.getLogger()
    for h in list(root.handlers):
        root.removeHandler(h)
    root.setLevel(logging.INFO)

    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    fh = logging.FileHandler(log_path, encoding="utf-8")
    fh.setFormatter(fmt)
    root.addHandler(fh)

    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(fmt)
    root.addHandler(sh)

    logging.getLogger(__name__).info("Logging to %s", log_path)
    return log_path
