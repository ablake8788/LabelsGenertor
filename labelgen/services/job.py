"""The settings for one job, parsed and validated from the form's text fields."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from labelgen.domain.boxes import BoxRange
from labelgen.domain.locations import staging_root


@dataclass(frozen=True)
class JobSettings:
    start_box: str
    end_box: str
    per_box: int
    box_step: str
    account: str
    env_folder: str
    vin: str
    output_folder: str
    labels_folder: str
    use_db: bool

    @classmethod
    def from_form(cls, form: Mapping[str, str]) -> "JobSettings":
        def text(key: str) -> str:
            return str(form.get(key, "") or "").strip()

        try:
            per_box = int(text("per_box"))
        except ValueError:
            raise ValueError("Labels per box must be a whole number.") from None
        return cls(
            start_box=text("start_box"),
            end_box=text("end_box"),
            per_box=per_box,
            box_step=text("box_step") or "1",
            account=text("account"),
            env_folder=text("env_folder"),
            vin=text("vin"),
            output_folder=text("output_folder"),
            labels_folder=text("labels_folder"),
            use_db=text("use_db") == "1",
        )

    def box_range(self) -> BoxRange:
        return BoxRange.from_text(self.start_box, self.end_box)

    @property
    def staging_root(self) -> str:
        return staging_root(self.env_folder, self.account)

    @property
    def print_list_folder(self) -> str:
        return self.labels_folder or self.output_folder
