"""
Composition root - Factory / dependency injection.

The only place that decides which concrete classes are used. Everything else receives its
collaborators, so tests (and future changes, e.g. another database) swap them here.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from labelgen.domain.generator import LabelGenerator
from labelgen.domain.guid import GuidProvider
from labelgen.infrastructure.config import IniConfigLoader
from labelgen.infrastructure.repository import LabelRepository, SqlServerLabelRepository
from labelgen.infrastructure.settings import SETTINGS_NAME, JsonSettingsStore
from labelgen.infrastructure.shell import Shell, WindowsShell
from labelgen.paths import app_dir as default_app_dir
from labelgen.services.label_service import LabelService


@dataclass
class Container:
    app_dir: Path
    config: IniConfigLoader
    settings: JsonSettingsStore
    shell: Shell
    service: LabelService


def build_container(app_dir: Path | None = None, *, shell: Shell | None = None,
                    guid_provider: GuidProvider | None = None,
                    repository: LabelRepository | None = None) -> Container:
    """Production wiring by default; pass shell / guid_provider / repository to override (tests)."""
    folder = Path(app_dir or default_app_dir())
    config = IniConfigLoader(folder)

    def repository_factory() -> LabelRepository:
        # A fresh repository per use: config.ini edits apply without restarting.
        return repository or SqlServerLabelRepository(config.connection_string())

    service = LabelService(LabelGenerator(guid_provider), repository_factory)
    return Container(
        app_dir=folder,
        config=config,
        settings=JsonSettingsStore(folder / SETTINGS_NAME),
        shell=shell or WindowsShell(),
        service=service,
    )
