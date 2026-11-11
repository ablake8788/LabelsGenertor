"""Infrastructure layer: everything that touches the outside world (config.ini, SQL Server, disk, printer)."""
from labelgen.infrastructure.config import ConfigError, DatabaseConfig, IniConfigLoader, masked
from labelgen.infrastructure.filesystem import BatchFileWriter, FolderCreator
from labelgen.infrastructure.repository import (
    InMemoryLabelRepository, LabelRepository, SqlServerLabelRepository, installed_sql_drivers,
)
from labelgen.infrastructure.settings import JsonSettingsStore
from labelgen.infrastructure.shell import RecordingShell, Shell, WindowsShell

__all__ = [
    "ConfigError", "DatabaseConfig", "IniConfigLoader", "masked",
    "BatchFileWriter", "FolderCreator",
    "InMemoryLabelRepository", "LabelRepository", "SqlServerLabelRepository", "installed_sql_drivers",
    "JsonSettingsStore",
    "RecordingShell", "Shell", "WindowsShell",
]
