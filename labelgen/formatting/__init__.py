"""
Formatting layer - Strategy pattern.

Every output of a batch (print list, folder .bat, database rows CSV) is a BatchFormatter,
so new outputs can be added without touching the rest of the app.
"""
from labelgen.formatting.base import BatchFormatter
from labelgen.formatting.db_rows import DB_COLUMNS, CsvFormatter, InventoryRowMapper
from labelgen.formatting.folder_script import FolderScriptFormatter
from labelgen.formatting.print_list import BOX_SEPARATOR, LIST_HEADER, SPACER, PrintListFormatter

__all__ = [
    "BatchFormatter",
    "DB_COLUMNS", "CsvFormatter", "InventoryRowMapper",
    "FolderScriptFormatter",
    "BOX_SEPARATOR", "LIST_HEADER", "SPACER", "PrintListFormatter",
]
