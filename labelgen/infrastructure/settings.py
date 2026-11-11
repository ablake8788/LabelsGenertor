"""The form values remembered between runs (label_app_settings.json next to the app)."""
from __future__ import annotations

import json
from pathlib import Path

SETTINGS_NAME = "label_app_settings.json"


class JsonSettingsStore:
    def __init__(self, path: Path):
        self.path = Path(path)

    def load(self) -> dict[str, str]:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}
        return {k: str(v) for k, v in data.items()} if isinstance(data, dict) else {}

    def save(self, values: dict[str, str]) -> None:
        try:
            self.path.write_text(json.dumps(values, indent=2), encoding="utf-8")
        except OSError:
            pass  # settings are a convenience; never block closing the app
