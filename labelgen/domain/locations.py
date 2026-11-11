"""Where label folders live (same rule as the stored procedure)."""
from __future__ import annotations

import ntpath

STAGING_SUBPATH = r"MorrisUniversalAutoGroup\PartsSale\Production\Current\0_staging"


def staging_root(environment_folder: str, account_folder: str) -> str:
    """@EnvironmetFolder + staging path + account, as a Windows path."""
    return ntpath.join(environment_folder.rstrip("\\/"), STAGING_SUBPATH, account_folder)
