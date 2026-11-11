"""Form values used the first time (later runs use label_app_settings.json)."""
from __future__ import annotations

from pathlib import Path

from labelgen.domain.locations import staging_root

ENV_FOLDER = r"C:\Users\ablak\MorrisAutoGroup Dropbox\Alexander Blake"
ACCOUNT = "LabelsSum"

DEFAULTS: dict[str, str] = {
    "start_box": "BX3718",
    "end_box": "BX3738",
    "per_box": "28",
    "box_step": "1",
    "account": ACCOUNT,
    "env_folder": ENV_FOLDER,
    "vin": "",
    "output_folder": str(Path.home() / "Documents" / "Labels"),
    "labels_folder": staging_root(ENV_FOLDER, ACCOUNT) + r"\print_labels_sum",
    "use_db": "1",
}

# Fields the form keeps between runs (everything except the batch itself).
FORM_KEYS = tuple(DEFAULTS)
