"""Rows for dbo.InventoryPartSale - column for column the same as the stored procedure's INSERT."""
from __future__ import annotations

import csv
import io

from labelgen.domain.models import LabelBatch
from labelgen.formatting.base import BatchFormatter

DB_COLUMNS = ("EbayAccount", "StockId", "ShortName", "LongName", "StockCategory", "StockStatus",
              "StockCondition", "LotId", "LotLocation", "CreatedBy", "CreatedOn", "PartAccountVin")


class InventoryRowMapper:
    """Maps a batch to database rows (tuples in DB_COLUMNS order)."""

    def __init__(self, ebay_account: str, part_account_vin: str = "", created_by: int = 1):
        self.ebay_account = ebay_account
        self.part_account_vin = part_account_vin or None   # empty VIN -> NULL
        self.created_by = created_by

    def to_rows(self, batch: LabelBatch) -> list[tuple]:
        name = f"& {self.ebay_account}"
        return [
            (self.ebay_account, label.text, name, name, "PART", "1_staging", "USED",
             label.text, label.box, self.created_by, batch.created_on, self.part_account_vin)
            for label in batch.labels
        ]


class CsvFormatter(BatchFormatter):
    """The database rows as CSV (saved with 'Save files' for checking/importing)."""

    def __init__(self, mapper: InventoryRowMapper):
        self.mapper = mapper

    def format(self, batch: LabelBatch) -> str:
        buf = io.StringIO(newline="")
        writer = csv.writer(buf)
        writer.writerow(DB_COLUMNS)
        writer.writerows(self.mapper.to_rows(batch))
        return buf.getvalue()
