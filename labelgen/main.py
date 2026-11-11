"""Entry point:  window by default,  --selftest / --check-db  for the self-test without a window."""
from __future__ import annotations

import sys

from labelgen.container import build_container
from labelgen.selftest import run_self_test


def main(argv: list[str] | None = None) -> None:
    args = sys.argv[1:] if argv is None else argv
    if "--selftest" in args or "--check-db" in args:
        sys.exit(run_self_test(check_db="--check-db" in args))

    # tkinter is imported only here, so the self-test and the tests run without it
    from labelgen.ui.controller import LabelController
    from labelgen.ui.tk_view import TkLabelView

    c = build_container()
    view = TkLabelView(c.settings, str(c.config.path))
    view.bind_controller(LabelController(view, c.service, c.config, c.shell))
    view.mainloop()
