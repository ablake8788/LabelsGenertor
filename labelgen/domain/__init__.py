"""Domain layer: boxes, labels and how labels are generated. No file, database or UI code here."""
from labelgen.domain.boxes import MAX_BOXES, BoxId, BoxRange, box_range
from labelgen.domain.generator import LabelGenerator
from labelgen.domain.guid import GuidProvider, RandomGuidProvider, SequenceGuidProvider
from labelgen.domain.locations import STAGING_SUBPATH, staging_root
from labelgen.domain.models import Label, LabelBatch

__all__ = [
    "MAX_BOXES", "BoxId", "BoxRange", "box_range",
    "LabelGenerator",
    "GuidProvider", "RandomGuidProvider", "SequenceGuidProvider",
    "STAGING_SUBPATH", "staging_root",
    "Label", "LabelBatch",
]
