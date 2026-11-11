"""
TkLabelView - the Tkinter window. It only builds widgets and forwards clicks to the controller;
all decisions live in LabelController. Colours and fonts come from theme.py.

    ┌ header: title ........................................ database badge ┐
    │ form panel             │ batch summary: boxes, labels, steps done       │
    │  Boxes                 │ ┌ Labels | Folder script | Rows | Connection ┐ │
    │  Destination           │ │  label roll preview                        │ │
    │  Folders               │ │                                            │ │
    │  [ Run all ]           │ └────────────────────────────────────────────┘ │
    │  One step at a time    │                                                │
    └ status bar ────────────────────────────────────────────────────────────┘
"""
from __future__ import annotations

import os
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import Sequence

from labelgen.domain.boxes import MAX_BOXES
from labelgen.formatting.db_rows import DB_COLUMNS
from labelgen.formatting.print_list import BOX_SEPARATOR, LIST_HEADER
from labelgen.infrastructure.settings import JsonSettingsStore
from labelgen.ui import theme as t
from labelgen.ui.controller import LabelController
from labelgen.ui.defaults import DEFAULTS, FORM_KEYS
from labelgen.ui.view import BatchState, DbState

STICKER_WIDTH = 24          # characters; every label is drawn on a sticker of the same width
SPACER_LINES = set(LIST_HEADER) | set(BOX_SEPARATOR)
WIDE_COLUMNS = {"StockId", "LotId", "CreatedOn", "PartAccountVin"}

DB_BADGES: dict[str, tuple[str, str, str]] = {   # state -> text, foreground, background
    "not_set_up": ("Database not set up", t.WARN, t.WARN_BG),
    "configured": ("Database configured", t.SLATE_TEXT, "#3A4853"),
    "connected": ("Database connected", t.OK, t.OK_BG),
    "failed": ("Database unreachable", t.ERROR, t.ERROR_BG),
}


def shorten_path(path: str, keep: int = 4) -> str:
    """'C:\\a\\b\\c\\d\\e\\f' -> '…\\c\\d\\e\\f' so long Dropbox paths fit on one line."""
    parts = path.replace("/", "\\").split("\\")
    return path if len(parts) <= keep + 1 else "…\\" + "\\".join(parts[-keep:])


class Badge(tk.Label):
    """Small rounded-looking status pill."""

    def __init__(self, parent, text: str, font, **kw):
        super().__init__(parent, text=text, font=font, padx=10, pady=3, bd=0, **kw)

    def set(self, text: str, fg: str, bg: str) -> None:
        self.configure(text=text, fg=fg, bg=bg)


class TkLabelView(tk.Tk):
    def __init__(self, settings: JsonSettingsStore, config_path: str):
        super().__init__()
        self.title("Roll Label Generator")
        self.geometry("1240x780")
        self.minsize(1080, 720)
        self.fonts = t.apply_theme(self)

        self._settings = settings
        self._config_path = config_path
        self.controller: LabelController | None = None
        self._syncing = False

        saved = {**DEFAULTS, **{k: v for k, v in settings.load().items() if k in FORM_KEYS}}
        self.vars = {k: tk.StringVar(value=saved[k]) for k in FORM_KEYS}
        self.vars["count"] = tk.StringVar()

        self._build()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def bind_controller(self, controller: LabelController) -> None:
        """Connect the presenter, then start keeping the linked fields in sync."""
        self.controller = controller
        self.vars["start_box"].trace_add("write", lambda *_: self._sync_count())
        self.vars["end_box"].trace_add("write", lambda *_: self._sync_count())
        self.vars["count"].trace_add("write", lambda *_: self._sync_end())
        for key in ("env_folder", "account"):
            self.vars[key].trace_add("write", lambda *_: self._update_root_preview())
        self._sync_count()
        self._update_root_preview()
        controller.refresh_connection_preview()
        self.set_batch_state(None)

    def _call(self, method: str):
        return lambda: getattr(self.controller, method)()

    # ================================================================== layout
    def _build(self) -> None:
        self._header()
        self.status = tk.StringVar(value="Enter a start and end box, then click Run all.")
        status = ttk.Frame(self, style="Panel.TFrame")
        status.pack(fill="x", side="bottom")
        ttk.Separator(status).pack(fill="x")
        ttk.Label(status, textvariable=self.status, style="Status.TLabel", anchor="w").pack(fill="x")

        body = ttk.Frame(self, padding=(16, 14, 16, 12))
        body.pack(fill="both", expand=True)
        body.columnconfigure(1, weight=1)
        body.rowconfigure(0, weight=1)
        self._form_panel(body).grid(row=0, column=0, sticky="nsw", padx=(0, 14))
        self._output_area(body).grid(row=0, column=1, sticky="nsew")

    def _header(self) -> None:
        bar = ttk.Frame(self, style="Header.TFrame", padding=(18, 12))
        bar.pack(fill="x")
        ttk.Label(bar, text="Roll Label Generator", style="Title.Header.TLabel").pack(side="left")
        ttk.Label(bar, text="Labels, Dropbox folders and inventory rows for a range of boxes",
                  style="Sub.Header.TLabel").pack(side="left", padx=(14, 0), pady=(5, 0))
        self.db_badge = Badge(bar, "", self.fonts.small)
        self.db_badge.pack(side="right")

    # ------------------------------------------------------------------ left: form
    def _form_panel(self, parent) -> ttk.Frame:
        panel = ttk.Frame(parent, style="Panel.TFrame", padding=(18, 14, 18, 16))
        panel.columnconfigure(1, weight=1)
        panel.columnconfigure(3, weight=1)
        self._row = 0

        def section(title: str) -> None:
            if self._row:
                ttk.Separator(panel).grid(row=self._row, column=0, columnspan=4, sticky="ew", pady=(10, 8))
                self._row += 1
            ttk.Label(panel, text=title, style="Section.Panel.TLabel")\
                .grid(row=self._row, column=0, columnspan=4, sticky="w", pady=(0, 4))
            self._row += 1

        def field(label: str, key: str, col: int = 0, spin: tuple[int, int] | None = None, span: int = 1):
            ttk.Label(panel, text=label, style="Panel.TLabel")\
                .grid(row=self._row, column=col, sticky="w", padx=(0 if col == 0 else 14, 8), pady=3)
            if spin:
                w = ttk.Spinbox(panel, from_=spin[0], to=spin[1], textvariable=self.vars[key], width=8)
            else:
                w = ttk.Entry(panel, textvariable=self.vars[key], width=11)
            w.grid(row=self._row, column=col + 1, columnspan=span, sticky="ew", pady=3)
            return w

        def folder(label: str, key: str) -> None:
            ttk.Label(panel, text=label, style="Panel.TLabel")\
                .grid(row=self._row, column=0, sticky="w", padx=(0, 8), pady=3)
            ttk.Entry(panel, textvariable=self.vars[key], width=22)\
                .grid(row=self._row, column=1, columnspan=2, sticky="ew", pady=3)
            ttk.Button(panel, text="Browse…", style="Browse.TButton", command=lambda: self._browse(key))\
                .grid(row=self._row, column=3, sticky="ew", padx=(6, 0), pady=3)
            self._row += 1

        section("Boxes")
        field("Start box", "start_box")
        field("End box", "end_box", col=2)
        self._row += 1
        field("Boxes", "count", spin=(1, MAX_BOXES))
        field("Labels per box", "per_box", col=2, spin=(1, 500))
        self._row += 1
        field("Account folder", "account")
        field("Box step", "box_step", col=2)
        self._row += 1
        field("Part account VIN", "vin", span=3)
        self._row += 1

        section("Folders")
        folder("Environment", "env_folder")
        self.root_preview = ttk.Label(panel, style="Path.Panel.TLabel")
        self.root_preview.grid(row=self._row, column=1, columnspan=3, sticky="w", pady=(0, 4))
        self._row += 1
        folder("Labels list", "labels_folder")
        folder(".bat and .csv", "output_folder")

        ttk.Separator(panel).grid(row=self._row, column=0, columnspan=4, sticky="ew", pady=(12, 12))
        self._row += 1
        ttk.Button(panel, text="Run all", style="Primary.TButton", command=self._call("run_all"))\
            .grid(row=self._row, column=0, columnspan=4, sticky="ew")
        self._row += 1
        ttk.Checkbutton(panel, text="Include database", variable=self.vars["use_db"], onvalue="1", offvalue="0")\
            .grid(row=self._row, column=0, columnspan=2, sticky="w", pady=(8, 0))
        ttk.Button(panel, text="Clear fields", style="Quiet.TButton", command=self._call("clear_fields"))\
            .grid(row=self._row, column=2, columnspan=2, sticky="e", pady=(8, 0))
        self._row += 1

        section("One step at a time")
        steps = ttk.Frame(panel, style="Panel.TFrame")
        steps.grid(row=self._row, column=0, columnspan=4, sticky="ew")
        for c in range(3):
            steps.columnconfigure(c, weight=1, uniform="steps")
        for i, (text, method) in enumerate([
            ("Generate labels", "generate"), ("Create folders", "create_folders"), ("Save files", "save_files"),
            ("Save labels list", "save_labels_list"), ("Copy labels", "copy_labels"), ("Print labels…", "print_labels"),
        ]):
            ttk.Button(steps, text=text, command=self._call(method))\
                .grid(row=i // 3, column=i % 3, sticky="ew", padx=(0 if i % 3 == 0 else 6, 0), pady=3)
        ttk.Button(steps, text="Save to database…", command=self._call("save_to_db"))\
            .grid(row=2, column=0, columnspan=3, sticky="ew", pady=3)
        return panel

    # ------------------------------------------------------------------ right: summary + tabs
    def _output_area(self, parent) -> ttk.Frame:
        area = ttk.Frame(parent)
        area.rowconfigure(1, weight=1)
        area.columnconfigure(0, weight=1)

        summary = ttk.Frame(area, padding=(2, 0, 0, 10))
        summary.grid(row=0, column=0, sticky="ew")
        self.fig_boxes, self.fig_labels, self.fig_range = (self._figure(summary, cap) for cap in
                                                           ("boxes", "labels", "range"))
        steps = ttk.Frame(summary)
        steps.pack(side="right", anchor="s", pady=(0, 2))
        self.step_badges = {key: Badge(steps, text, self.fonts.small)
                            for key, text in (("folders", "Folders"), ("print", "Print list"), ("db", "Database"))}
        for b in self.step_badges.values():
            b.pack(side="left", padx=(6, 0))

        nb = ttk.Notebook(area)
        nb.grid(row=1, column=0, sticky="nsew")
        self.roll = self._roll_tab(nb)
        self._draw_roll("")
        self.txt_script = self._script_tab(nb)
        self._rows_tab(nb)
        self._db_tab(nb)
        return area

    def _figure(self, parent, caption: str) -> ttk.Label:
        box = ttk.Frame(parent)
        box.pack(side="left", padx=(0, 28))
        value = ttk.Label(box, text="–", style="Figure.TLabel")
        value.pack(anchor="w")
        ttk.Label(box, text=caption, style="FigureCaption.TLabel").pack(anchor="w")
        return value

    def _scrolled_text(self, nb: ttk.Notebook, title: str, **text_kw) -> tk.Text:
        frame = ttk.Frame(nb, style="Panel.TFrame")
        nb.add(frame, text=title)
        txt = tk.Text(frame, wrap="none", undo=False, bd=0, highlightthickness=0, **text_kw)
        ys = ttk.Scrollbar(frame, orient="vertical", command=txt.yview)
        txt.configure(yscrollcommand=ys.set)
        ys.pack(side="right", fill="y")
        txt.pack(side="left", fill="both", expand=True)
        return txt

    def _roll_tab(self, nb: ttk.Notebook) -> tk.Text:
        """The print list drawn as a label roll: white stickers on a grey liner."""
        roll = self._scrolled_text(nb, "Labels", bg=t.ROLL_LINER, fg=t.ROLL_INK, font=self.fonts.mono,
                                   padx=0, pady=14, cursor="arrow")
        margin = 28
        roll.tag_configure("label", background=t.ROLL_LABEL, foreground=t.ROLL_INK, font=self.fonts.mono_bold,
                           lmargin1=margin, lmargin2=margin, lmargincolor=t.ROLL_LINER)
        roll.tag_configure("gap", font=(self.fonts.mono[0], 3))
        roll.tag_configure("spacer", foreground=t.ROLL_SEPARATOR, lmargin1=margin)
        roll.tag_configure("empty", foreground=t.MUTED, font=self.fonts.body, lmargin1=margin, spacing1=40)
        return roll

    def _script_tab(self, nb: ttk.Notebook) -> tk.Text:
        return self._scrolled_text(nb, "Folder script", bg=t.SURFACE, fg=t.INK, font=self.fonts.mono,
                                   padx=14, pady=12)

    def _rows_tab(self, nb: ttk.Notebook) -> None:
        frame = ttk.Frame(nb, style="Panel.TFrame")
        nb.add(frame, text="Database rows")
        self.tree = ttk.Treeview(frame, columns=DB_COLUMNS, show="headings")
        for c in DB_COLUMNS:
            self.tree.heading(c, text=c, anchor="w")
            self.tree.column(c, width=150 if c in WIDE_COLUMNS else 118, stretch=False, anchor="w")
        self.tree.tag_configure("alt", background=t.ROW_ALT)
        ys = ttk.Scrollbar(frame, orient="vertical", command=self.tree.yview)
        xs = ttk.Scrollbar(frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=ys.set, xscrollcommand=xs.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        ys.grid(row=0, column=1, sticky="ns")
        xs.grid(row=1, column=0, sticky="ew")
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)

    def _db_tab(self, nb: ttk.Notebook) -> None:
        frame = ttk.Frame(nb, style="Panel.TFrame", padding=(18, 16))
        nb.add(frame, text="Database connection")
        ttk.Label(frame, text="Connection", style="Section.Panel.TLabel").pack(anchor="w")
        ttk.Label(frame, text=f"Read from {self._config_path}", style="Muted.Panel.TLabel")\
            .pack(anchor="w", pady=(2, 10))
        self.conn_preview = ttk.Label(frame, style="Panel.TLabel", justify="left", font=self.fonts.mono)
        frame.bind("<Configure>", lambda e: self.conn_preview.configure(wraplength=max(200, e.width - 40)))
        self.conn_preview.pack(anchor="w", pady=(0, 14))
        buttons = ttk.Frame(frame, style="Panel.TFrame")
        buttons.pack(anchor="w")
        for text, method in [("Test connection", "test_connection"), ("Open config.ini", "open_config"),
                             ("Reload config.ini", "refresh_connection_preview")]:
            ttk.Button(buttons, text=text, command=self._call(method)).pack(side="left", padx=(0, 8))
        ttk.Label(frame, text="The password is never shown here. Edit config.ini, then click Reload.",
                  style="Muted.Panel.TLabel").pack(anchor="w", pady=(14, 0))

    # ================================================================== linked fields
    def _sync_count(self) -> None:
        if self._syncing or not self.controller:
            return
        n = self.controller.count_for(self.vars["start_box"].get(), self.vars["end_box"].get())
        if n is not None:
            self.set_fields({"count": n})

    def _sync_end(self) -> None:
        if self._syncing or not self.controller:
            return
        end = self.controller.end_for(self.vars["start_box"].get(), self.vars["count"].get())
        if end is not None:
            self.set_fields({"end_box": end})

    def _update_root_preview(self) -> None:
        root = self.controller.root_preview(self.vars["env_folder"].get(), self.vars["account"].get())
        self.root_preview.config(text=f"Label folders go to {shorten_path(root)}")

    def _browse(self, key: str) -> None:
        d = filedialog.askdirectory(initialdir=self.vars[key].get() or None)
        if d:
            self.vars[key].set(os.path.normpath(d))

    def _on_close(self) -> None:
        self._settings.save({k: self.vars[k].get() for k in FORM_KEYS})
        self.destroy()

    # ================================================================== LabelView protocol
    def get_form(self) -> dict[str, str]:
        return {k: v.get() for k, v in self.vars.items()}

    def set_fields(self, values: dict[str, str]) -> None:
        self._syncing = True
        try:
            for k, v in values.items():
                self.vars[k].set(v)
        finally:
            self._syncing = False

    def show_error(self, title: str, message: str) -> None:
        messagebox.showerror(title, message, parent=self)

    def show_info(self, title: str, message: str) -> None:
        messagebox.showinfo(title, message, parent=self)

    def show_warning(self, title: str, message: str) -> None:
        messagebox.showwarning(title, message, parent=self)

    def ask_yes_no(self, title: str, message: str, warning: bool = False) -> bool:
        return messagebox.askyesno(title, message, icon="warning" if warning else "question", parent=self)

    def set_status(self, text: str) -> None:
        self.status.set(text)
        self.update_idletasks()

    def show_batch(self, print_list: str, folder_script: str, rows: Sequence[tuple]) -> None:
        self._draw_roll(print_list)
        self._set_text(self.txt_script, folder_script)
        self.tree.delete(*self.tree.get_children())
        for i, r in enumerate(rows):
            self.tree.insert("", "end", values=["" if v is None else v for v in r], tags=("alt",) if i % 2 else ())

    def clear_batch(self) -> None:
        self._draw_roll("")
        self._set_text(self.txt_script, "")
        self.tree.delete(*self.tree.get_children())

    def set_batch_state(self, state: BatchState | None) -> None:
        if state is None:
            for w in (self.fig_boxes, self.fig_labels, self.fig_range):
                w.config(text="–")
            done = {"folders": False, "print": False, "db": False}
        else:
            self.fig_boxes.config(text=str(state.boxes))
            self.fig_labels.config(text=str(state.labels))
            self.fig_range.config(text=state.first_box if state.boxes == 1 else f"{state.first_box} – {state.last_box}")
            done = {"folders": state.folders_created, "print": state.print_list_saved, "db": state.saved_to_db}
        names = {"folders": "Folders", "print": "Print list", "db": "Database"}
        for key, badge in self.step_badges.items():
            if done[key]:
                badge.set(f"✓ {names[key]}", t.OK, t.OK_BG)
            else:
                badge.set(names[key], t.MUTED, t.IDLE_BG)

    def set_clipboard(self, text: str) -> None:
        self.clipboard_clear()
        self.clipboard_append(text)

    def set_connection_preview(self, text: str) -> None:
        self.conn_preview.config(text=text)

    def set_db_state(self, state: DbState) -> None:
        self.db_badge.set(*DB_BADGES[state])

    # ================================================================== helpers
    def _draw_roll(self, print_list: str) -> None:
        roll = self.roll
        roll.configure(state="normal")
        roll.delete("1.0", "end")
        if not print_list:
            roll.insert("end", "No labels yet. Enter a box range and click Run all or Generate labels.", "empty")
        for line in print_list.splitlines():
            if line in SPACER_LINES:
                roll.insert("end", line, "spacer")
            else:
                roll.insert("end", f"  {line}".ljust(STICKER_WIDTH), "label")
                roll.insert("end", "\n\n", "gap")      # thin strip of liner between stickers
                continue
            roll.insert("end", "\n")
        roll.configure(state="disabled")

    @staticmethod
    def _set_text(widget: tk.Text, text: str) -> None:
        widget.delete("1.0", "end")
        widget.insert("1.0", text)
