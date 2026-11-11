"""
UI layer - Model-View-Presenter.

LabelController (presenter): all button logic. Never imports tkinter, so it is fully testable.
LabelView (protocol)       : what the controller needs from a window.
TkLabelView                : the Tkinter window; only draws widgets and forwards clicks.
"""
from labelgen.ui.controller import LabelController
from labelgen.ui.defaults import DEFAULTS
from labelgen.ui.view import LabelView

__all__ = ["DEFAULTS", "LabelController", "LabelView"]
