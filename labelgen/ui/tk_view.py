"""
TkLabelView - the Tkinter window. It only builds widgets and forwards clicks to the controller;
all decisions live in LabelController.
"""
from __future__ import annotations

import os
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import Sequence

from labelgen.domain.boxes import MAX_BOXES
from labelgen.formatting.db_rows import DB_COLUMNS
from labelgen.infrastructure.settings import JsonSettingsStore
from labelgen.ui.controller import LabelController
from labelgen.ui.defaults import DEFAULTS, FORM_KEYS


class TkLabelView(tk.Tk):
    def __init__(self, settings: JsonSettingsStore, config_path: str):
        super().__init__()
        self.title("eBay Roll Label Generator")
        self.geometry("1050x720")
        self.minsize(900, 600)

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

    def _call(self, method: str):
        return lambda: getattr(self.controller, method)()

    # ------------------------------------------------------------------ layout
    def _build(self) -> None:
        pad = {"padx": 6, "pady": 3}
        form = ttk.LabelFrame(self, text="Settings")
        form.pack(fill="x", padx=10, pady=(10, 4))

        def entry(row, col, label, key, width=14, span=1):
            ttk.Label(form, text=label).grid(row=row, column=col, sticky="e", **pad)
            ttk.Entry(form, textvariable=self.vars[key], width=width)\
                .grid(row=row, column=col + 1, columnspan=span, sticky="we", **pad)

        def folder(row, label, key):
            ttk.Label(form, text=label).grid(row=row, column=0, sticky="e", **pad)
            ttk.Entry(form, textvariable=self.vars[key]).grid(row=row, column=1, columnspan=6, sticky="we", **pad)
            ttk.Button(form, text="Browse…", command=lambda: self._browse(key)).grid(row=row, column=7, sticky="w", **pad)

        entry(0, 0, "Start box", "start_box")
        entry(0, 2, "End box", "end_box")
        ttk.Label(form, text="Number of boxes").grid(row=0, column=4, sticky="e", **pad)
        ttk.Spinbox(form, from_=1, to=MAX_BOXES, textvariable=self.vars["count"], width=8)\
            .grid(row=0, column=5, sticky="w", **pad)
        ttk.Label(form, text="Labels per box").grid(row=0, column=6, sticky="e", **pad)
        ttk.Spinbox(form, from_=1, to=500, textvariable=self.vars["per_box"], width=8)\
            .grid(row=0, column=7, sticky="w", **pad)

        entry(1, 0, "Box step", "box_step")
        entry(1, 2, "Account folder", "account")
        entry(1, 4, "Part account VIN", "vin", width=22, span=3)

        folder(2, "Environment folder", "env_folder")
        ttk.Label(form, text="Root folder").grid(row=3, column=0, sticky="e", **pad)
        self.root_preview = ttk.Label(form, foreground="#555")
        self.root_preview.grid(row=3, column=1, columnspan=7, sticky="w", **pad)
        folder(4, "Save files to", "output_folder")
        folder(5, "Labels list folder", "labels_folder")
        for c in (1, 3):
            form.columnconfigure(c, weight=1)

        bar = ttk.Frame(self)
        bar.pack(fill="x", padx=10, pady=4)
        ttk.Button(bar, text="▶ Run all", command=self._call("run_all")).pack(side="left", padx=(0, 6))
        ttk.Checkbutton(bar, text="Include database", variable=self.vars["use_db"],
                        onvalue="1", offvalue="0").pack(side="left", padx=(0, 14))
        ttk.Separator(bar, orient="vertical").pack(side="left", fill="y", padx=6)
        for text, method in [("Generate labels", "generate"), ("Create folders now", "create_folders"),
                             ("Save files", "save_files"), ("Copy labels", "copy_labels"),
                             ("Save labels list", "save_labels_list"), ("Print labels…", "print_labels")]:
            ttk.Button(bar, text=text, command=self._call(method)).pack(side="left", padx=6)
        ttk.Button(bar, text="Save to database…", command=self._call("save_to_db")).pack(side="right")
        ttk.Button(bar, text="Clear fields", command=self._call("clear_fields")).pack(side="right", padx=6)

        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=10, pady=4)
        self.txt_labels = self._text_tab(nb, "Labels (print)")
        self.txt_script = self._text_tab(nb, "Folder script (.bat)")
        self._rows_tab(nb)
        self._db_tab(nb)

        self.status = tk.StringVar(value="Set the start and end box, then click Generate labels.")
        ttk.Label(self, textvariable=self.status, relief="sunken", anchor="w").pack(fill="x", side="bottom")

    def _text_tab(self, nb: ttk.Notebook, title: str) -> tk.Text:
        frame = ttk.Frame(nb)
        nb.add(frame, text=title)
        txt = tk.Text(frame, font=("Consolas", 11), wrap="none", undo=False)
        ys = ttk.Scrollbar(frame, orient="vertical", command=txt.yview)
        txt.configure(yscrollcommand=ys.set)
        txt.pack(side="left", fill="both", expand=True)
        ys.pack(side="right", fill="y")
        return txt

    def _rows_tab(self, nb: ttk.Notebook) -> None:
        frame = ttk.Frame(nb)
        nb.add(frame, text="Database rows")
        self.tree = ttk.Treeview(frame, columns=DB_COLUMNS, show="headings")
        for c in DB_COLUMNS:
            self.tree.heading(c, text=c)
            self.tree.column(c, width=110, stretch=False)
        ys = ttk.Scrollbar(frame, orient="vertical", command=self.tree.yview)
        xs = ttk.Scrollbar(frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=ys.set, xscrollcommand=xs.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        ys.grid(row=0, column=1, sticky="ns")
        xs.grid(row=1, column=0, sticky="ew")
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)

    def _db_tab(self, nb: ttk.Notebook) -> None:
        frame = ttk.Frame(nb)
        nb.add(frame, text="Database connection")
        ttk.Label(frame, text=f"Connection is read from:  {self._config_path}").pack(anchor="w", padx=8, pady=(10, 2))
        self.conn_preview = ttk.Label(frame, foreground="#555", wraplength=950, justify="left")
        self.conn_preview.pack(anchor="w", padx=8, pady=4)
        buttons = ttk.Frame(frame)
        buttons.pack(anchor="w", padx=8, pady=8)
        for text, method in [("Open config.ini", "open_config"), ("Reload config.ini", "refresh_connection_preview"),
                             ("Test connection", "test_connection")]:
            ttk.Button(buttons, text=text, command=self._call(method)).pack(side="left", padx=(0, 6))

    # ------------------------------------------------------------------ linked fields
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
        self.root_preview.config(text=self.controller.root_preview(self.vars["env_folder"].get(),
                                                                   self.vars["account"].get()))

    def _browse(self, key: str) -> None:
        d = filedialog.askdirectory(initialdir=self.vars[key].get() or None)
        if d:
            self.vars[key].set(os.path.normpath(d))

    def _on_close(self) -> None:
        self._settings.save({k: self.vars[k].get() for k in FORM_KEYS})
        self.destroy()

    # ------------------------------------------------------------------ LabelView protocol
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
        messagebox.showerror(title, message)

    def show_info(self, title: str, message: str) -> None:
        messagebox.showinfo(title, message)

    def show_warning(self, title: str, message: str) -> None:
        messagebox.showwarning(title, message)

    def ask_yes_no(self, title: str, message: str, warning: bool = False) -> bool:
        return messagebox.askyesno(title, message, icon="warning" if warning else "question")

    def set_status(self, text: str) -> None:
        self.status.set(text)
        self.update_idletasks()

    def show_batch(self, print_list: str, folder_script: str, rows: Sequence[tuple]) -> None:
        self._set_text(self.txt_labels, print_list)
        self._set_text(self.txt_script, folder_script)
        self.tree.delete(*self.tree.get_children())
        for r in rows:
            self.tree.insert("", "end", values=["" if v is None else v for v in r])

    def clear_batch(self) -> None:
        self._set_text(self.txt_labels, "")
        self._set_text(self.txt_script, "")
        self.tree.delete(*self.tree.get_children())

    def set_clipboard(self, text: str) -> None:
        self.clipboard_clear()
        self.clipboard_append(text)

    def set_connection_preview(self, text: str) -> None:
        self.conn_preview.config(text=text)

    @staticmethod
    def _set_text(widget: tk.Text, text: str) -> None:
        widget.delete("1.0", "end")
        widget.insert("1.0", text)
