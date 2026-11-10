"""
eBay Roll Label Generator - desktop front end (Tkinter).

Run:   python label_app.py
"""
from __future__ import annotations

import csv
import json
import os
import sys
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

import label_config as cfg
import label_core as core

# Next to the .exe when built with PyInstaller, otherwise next to this script.
APP_DIR = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).parent
SETTINGS_FILE = APP_DIR / "label_app_settings.json"
DEFAULTS = {
    "start_box": "BX3718",
    "end_box": "BX3738",
    "per_box": "28",
    "box_step": "1",
    "account": "LabelsSum",
    "env_folder": r"C:\Users\ablak\MorrisAutoGroup Dropbox\Alexander Blake",
    "vin": "",
    "output_folder": str(Path.home() / "Documents" / "Labels"),
    "labels_folder": core.root_folder(r"C:\Users\ablak\MorrisAutoGroup Dropbox\Alexander Blake", "LabelsSum")
                     + r"\print_labels_sum",
    "use_db": "1",
}


class LabelApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("eBay Roll Label Generator")
        self.geometry("1050x720")
        self.minsize(900, 600)

        self.labels_by_box: dict = {}
        self.labels_path: Path | None = None
        self.generated_at: datetime | None = None
        self.saved_to_db = False
        self._syncing = False

        settings = {**DEFAULTS, **self._load_settings()}
        settings.pop("conn_str", None)  # connection now lives in config.ini
        self.vars = {k: tk.StringVar(value=v) for k, v in settings.items()}
        self.count_var = tk.StringVar()

        self._build_ui()
        self._sync_count_from_end()
        self.vars["start_box"].trace_add("write", lambda *_: self._sync_count_from_end())
        self.vars["end_box"].trace_add("write", lambda *_: self._sync_count_from_end())
        self.count_var.trace_add("write", lambda *_: self._sync_end_from_count())
        for k in ("env_folder", "account"):
            self.vars[k].trace_add("write", lambda *_: self._update_root_preview())
        self._update_root_preview()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ------------------------------------------------------------------ layout
    def _build_ui(self):
        pad = {"padx": 6, "pady": 3}
        form = ttk.LabelFrame(self, text="Settings")
        form.pack(fill="x", padx=10, pady=(10, 4))

        def entry(row, col, label, key, width=14, var=None):
            ttk.Label(form, text=label).grid(row=row, column=col, sticky="e", **pad)
            e = ttk.Entry(form, textvariable=var or self.vars[key], width=width)
            e.grid(row=row, column=col + 1, sticky="we", **pad)
            return e

        entry(0, 0, "Start box", "start_box")
        entry(0, 2, "End box", "end_box")
        ttk.Label(form, text="Number of boxes").grid(row=0, column=4, sticky="e", **pad)
        ttk.Spinbox(form, from_=1, to=core.MAX_BOXES, textvariable=self.count_var, width=8)\
            .grid(row=0, column=5, sticky="w", **pad)
        ttk.Label(form, text="Labels per box").grid(row=0, column=6, sticky="e", **pad)
        ttk.Spinbox(form, from_=1, to=500, textvariable=self.vars["per_box"], width=8)\
            .grid(row=0, column=7, sticky="w", **pad)

        entry(1, 0, "Box step", "box_step")
        entry(1, 2, "Account folder", "account")
        entry(1, 4, "Part account VIN", "vin", width=22).grid(columnspan=3)

        ttk.Label(form, text="Environment folder").grid(row=2, column=0, sticky="e", **pad)
        ttk.Entry(form, textvariable=self.vars["env_folder"]).grid(row=2, column=1, columnspan=6, sticky="we", **pad)
        ttk.Button(form, text="Browse…", command=lambda: self._browse("env_folder")).grid(row=2, column=7, sticky="w", **pad)

        ttk.Label(form, text="Root folder").grid(row=3, column=0, sticky="e", **pad)
        self.root_preview = ttk.Label(form, foreground="#555")
        self.root_preview.grid(row=3, column=1, columnspan=7, sticky="w", **pad)

        ttk.Label(form, text="Save files to").grid(row=4, column=0, sticky="e", **pad)
        ttk.Entry(form, textvariable=self.vars["output_folder"]).grid(row=4, column=1, columnspan=6, sticky="we", **pad)
        ttk.Button(form, text="Browse…", command=lambda: self._browse("output_folder")).grid(row=4, column=7, sticky="w", **pad)

        ttk.Label(form, text="Labels list folder").grid(row=5, column=0, sticky="e", **pad)
        ttk.Entry(form, textvariable=self.vars["labels_folder"]).grid(row=5, column=1, columnspan=6, sticky="we", **pad)
        ttk.Button(form, text="Browse…", command=lambda: self._browse("labels_folder")).grid(row=5, column=7, sticky="w", **pad)
        for c in (1, 3):
            form.columnconfigure(c, weight=1)

        bar = ttk.Frame(self)
        bar.pack(fill="x", padx=10, pady=4)
        ttk.Button(bar, text="▶ Run all", command=self.run_all).pack(side="left", padx=(0, 6))
        ttk.Checkbutton(bar, text="Include database", variable=self.vars["use_db"],
                        onvalue="1", offvalue="0").pack(side="left", padx=(0, 14))
        ttk.Separator(bar, orient="vertical").pack(side="left", fill="y", padx=6)
        ttk.Button(bar, text="Generate labels", command=self.generate).pack(side="left", padx=6)
        ttk.Button(bar, text="Create folders now", command=self.create_folders).pack(side="left", padx=6)
        ttk.Button(bar, text="Save files", command=self.save_files).pack(side="left", padx=6)
        ttk.Button(bar, text="Copy labels", command=self.copy_labels).pack(side="left", padx=6)
        ttk.Button(bar, text="Save labels list", command=self.save_labels_list).pack(side="left", padx=6)
        ttk.Button(bar, text="Print labels…", command=self.print_labels).pack(side="left", padx=6)
        ttk.Button(bar, text="Save to database…", command=self.save_to_db).pack(side="right")
        ttk.Button(bar, text="Clear fields", command=self.clear_fields).pack(side="right", padx=6)

        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=10, pady=4)
        self.txt_labels = self._text_tab(nb, "Labels (print)")
        self.txt_script = self._text_tab(nb, "Folder script (.bat)")

        tree_frame = ttk.Frame(nb)
        nb.add(tree_frame, text="Database rows")
        self.tree = ttk.Treeview(tree_frame, columns=core.DB_COLUMNS, show="headings")
        for c in core.DB_COLUMNS:
            self.tree.heading(c, text=c)
            self.tree.column(c, width=110, stretch=False)
        ys = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        xs = ttk.Scrollbar(tree_frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=ys.set, xscrollcommand=xs.set)
        self.tree.grid(row=0, column=0, sticky="nsew"); ys.grid(row=0, column=1, sticky="ns"); xs.grid(row=1, column=0, sticky="ew")
        tree_frame.rowconfigure(0, weight=1); tree_frame.columnconfigure(0, weight=1)

        db_frame = ttk.Frame(nb)
        nb.add(db_frame, text="Database connection")
        ttk.Label(db_frame, text=f"Connection is read from:  {cfg.config_path(APP_DIR)}").pack(anchor="w", padx=8, pady=(10, 2))
        self.conn_preview = ttk.Label(db_frame, foreground="#555", wraplength=950, justify="left")
        self.conn_preview.pack(anchor="w", padx=8, pady=4)
        btns = ttk.Frame(db_frame)
        btns.pack(anchor="w", padx=8, pady=8)
        ttk.Button(btns, text="Open config.ini", command=self.open_config).pack(side="left", padx=(0, 6))
        ttk.Button(btns, text="Reload config.ini", command=self._show_conn).pack(side="left", padx=6)
        ttk.Button(btns, text="Test connection", command=self.test_db).pack(side="left", padx=6)
        self._show_conn()

        self.status = tk.StringVar(value="Set the start and end box, then click Generate labels.")
        ttk.Label(self, textvariable=self.status, relief="sunken", anchor="w").pack(fill="x", side="bottom")

    def _text_tab(self, nb, title):
        frame = ttk.Frame(nb)
        nb.add(frame, text=title)
        txt = tk.Text(frame, font=("Consolas", 11), wrap="none", undo=False)
        ys = ttk.Scrollbar(frame, orient="vertical", command=txt.yview)
        txt.configure(yscrollcommand=ys.set)
        txt.pack(side="left", fill="both", expand=True); ys.pack(side="right", fill="y")
        return txt

    # ------------------------------------------------------------------ syncing fields
    def _sync_count_from_end(self):
        if self._syncing:
            return
        try:
            n = len(core.box_range(self.vars["start_box"].get(), self.vars["end_box"].get()))
        except ValueError:
            return
        self._syncing = True
        self.count_var.set(str(n))
        self._syncing = False

    def _sync_end_from_count(self):
        if self._syncing:
            return
        try:
            boxes = core.box_range(self.vars["start_box"].get(), count=int(self.count_var.get()))
        except (ValueError, TypeError):
            return
        self._syncing = True
        self.vars["end_box"].set(boxes[-1])
        self._syncing = False

    def _update_root_preview(self):
        self.root_preview.config(text=self._root_path())

    def _root_path(self):
        return core.root_folder(self.vars["env_folder"].get(), self.vars["account"].get())

    def _browse(self, key):
        d = filedialog.askdirectory(initialdir=self.vars[key].get() or None)
        if d:
            self.vars[key].set(os.path.normpath(d))

    # ------------------------------------------------------------------ actions
    def generate(self):
        try:
            boxes = core.box_range(self.vars["start_box"].get(), self.vars["end_box"].get())
            per_box = int(self.vars["per_box"].get())
            if not self.vars["account"].get().strip():
                raise ValueError("Account folder is required.")
            self.labels_by_box = core.generate_labels(boxes, per_box)
        except ValueError as e:
            messagebox.showerror("Check settings", str(e))
            return False
        self.generated_at = datetime.now()
        self.saved_to_db = False
        self.labels_path = None
        step = self.vars["box_step"].get().strip() or "1"

        self._set_text(self.txt_labels, core.labels_text(self.labels_by_box))
        self._set_text(self.txt_script, core.mkdir_script(self.labels_by_box, self._root_path(), step).replace("\r\n", "\n"))
        self.tree.delete(*self.tree.get_children())
        for r in self._rows():
            self.tree.insert("", "end", values=[("" if v is None else v) for v in r])

        total = sum(len(v) for v in self.labels_by_box.values())
        self.status.set(f"Generated {total} labels for {len(boxes)} boxes ({boxes[0]} – {boxes[-1]}). "
                        f"Not saved to the database yet.")
        return True

    def _rows(self):
        return core.db_rows(self.labels_by_box, self.vars["account"].get().strip(),
                            self.vars["vin"].get().strip(), created_on=self.generated_at)

    def _need_labels(self):
        if not self.labels_by_box:
            messagebox.showinfo("Nothing yet", "Click Generate labels first.")
            return False
        return True

    def _range_tag(self):
        boxes = list(self.labels_by_box)
        return boxes[0] if len(boxes) == 1 else f"{boxes[0]}-{boxes[-1]}"

    def save_files(self):
        if not self._need_labels():
            return
        try:
            paths = self._write_files()
        except OSError as e:
            messagebox.showerror("File error", str(e))
            return
        self.status.set(f"Saved labels list to {paths[0].parent} and 2 files to {paths[1].parent}")
        messagebox.showinfo("Saved", "Saved:\n\n" + "\n".join(str(p) for p in paths))

    def _write_labels_list(self):
        """Write the print list .txt to the 'Labels list folder'. Returns its path."""
        folder = Path(self.vars["labels_folder"].get().strip() or self.vars["output_folder"].get())
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / f"labels_{self._range_tag()}_{self.generated_at:%Y%m%d_%H%M%S}.txt"
        path.write_text(core.labels_text(self.labels_by_box), encoding="utf-8")
        self.labels_path = path
        return path

    def save_labels_list(self):
        if not self._need_labels():
            return
        try:
            path = self._write_labels_list()
        except OSError as e:
            messagebox.showerror("Save labels list", str(e))
            return
        self.status.set(f"Labels list saved: {path}")
        messagebox.showinfo("Save labels list", f"Saved:\n\n{path}")

    def _write_files(self):
        """Labels .txt -> Labels list folder; folder .bat and DB rows .csv -> Save files to. Returns the three paths."""
        out = Path(self.vars["output_folder"].get())
        out.mkdir(parents=True, exist_ok=True)
        tag = f"{self._range_tag()}_{self.generated_at:%Y%m%d_%H%M%S}"
        step = self.vars["box_step"].get().strip() or "1"

        bat_path = out / f"create_folders_{tag}.bat"
        csv_path = out / f"db_rows_{tag}.csv"
        labels_path = self._write_labels_list()
        bat_path.write_bytes(core.mkdir_script(self.labels_by_box, self._root_path(), step).encode("cp1252", "replace"))
        with csv_path.open("w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(core.DB_COLUMNS)
            w.writerows(self._rows())
        return [labels_path, bat_path, csv_path]

    def print_labels(self):
        """Send the labels list (.txt) to the default Windows printer."""
        if not self._need_labels():
            return
        try:
            if not (self.labels_path and self.labels_path.exists()):
                self._write_labels_list()
        except OSError as e:
            messagebox.showerror("Print", str(e))
            return
        total = sum(len(v) for v in self.labels_by_box.values())
        if not messagebox.askyesno("Print labels", f"Print {total} labels to your default printer?\n\n{self.labels_path.name}"):
            return
        try:
            os.startfile(str(self.labels_path), "print")
        except (AttributeError, OSError) as e:
            messagebox.showerror("Print", f"Could not print:\n{e}\n\nThe list is saved here:\n{self.labels_path}")
            return
        self.status.set(f"Sent {total} labels to the printer ({self.labels_path.name}).")

    def clear_fields(self):
        """Clear the box range, VIN and the generated batch. Folders, account and DB settings are kept."""
        if self.labels_by_box and not self.saved_to_db and self.vars["use_db"].get() == "1":
            if not messagebox.askyesno("Clear fields", "This batch hasn't been saved to the database. Clear it anyway?"):
                return
        self._syncing = True
        for k in ("start_box", "end_box", "vin"):
            self.vars[k].set("")
        self.count_var.set("")
        self._syncing = False
        self.labels_by_box = {}
        self.labels_path = None
        self.generated_at = None
        self.saved_to_db = False
        self._set_text(self.txt_labels, "")
        self._set_text(self.txt_script, "")
        self.tree.delete(*self.tree.get_children())
        self.status.set("Cleared. Enter a start and end box, then click Run all.")

    def copy_labels(self):
        if not self._need_labels():
            return
        self.clipboard_clear()
        self.clipboard_append(core.labels_text(self.labels_by_box))
        self.status.set("Labels copied to clipboard.")

    def create_folders(self):
        if not self._need_labels():
            return
        root = Path(self._root_path())
        step = self.vars["box_step"].get().strip() or "1"
        paths = core.folder_paths(self.labels_by_box, step)
        if not messagebox.askyesno("Create folders", f"Create {len(paths)} folders under:\n\n{root}?"):
            return
        try:
            made = self._make_folders()
        except OSError as e:
            messagebox.showerror("Folder error", str(e))
            return
        self.status.set(f"Created {made} folders under {root}")

    def _make_folders(self):
        """Create <root>\\<box>\\<step>\\<label> for every label. Returns how many were new."""
        root = Path(self._root_path())
        step = self.vars["box_step"].get().strip() or "1"
        made = 0
        for box, st, label in core.folder_paths(self.labels_by_box, step):
            p = root / box / st / label
            if not p.exists():
                p.mkdir(parents=True)
                made += 1
        return made

    # ------------------------------------------------------------------ run all
    def run_all(self):
        """1 generate labels  2 create folders  3 save/open print list  4 save to database."""
        use_db = self.vars["use_db"].get() == "1"
        try:
            boxes = core.box_range(self.vars["start_box"].get(), self.vars["end_box"].get())
            per_box = int(self.vars["per_box"].get())
        except ValueError as e:
            messagebox.showerror("Check settings", str(e))
            return

        # Check the database BEFORE creating anything, so a duplicate box stops the run cleanly.
        warning = ""
        if use_db:
            try:
                import label_db
                existing = label_db.existing_boxes(self._conn_str(), boxes)
            except Exception as e:
                messagebox.showerror("Database", f"Can't reach the database, nothing was created.\n\n{e}\n\n"
                                     "Fix the connection or untick 'Include database'.")
                return
            if existing:
                warning = "\n\nWARNING - these boxes already have rows in the database:\n" + \
                          "\n".join(f"  {b}: {n} rows" for b, n in existing.items())

        steps = ["create the folders", "save and open the print list"] + (["save to the database"] if use_db else [])
        msg = (f"Generate {len(boxes) * per_box} labels for {len(boxes)} boxes ({boxes[0]} – {boxes[-1]}), "
               f"then {', '.join(steps)}?\n\nFolders go under:\n{self._root_path()}{warning}")
        if not messagebox.askyesno("Run all", msg, icon="warning" if warning else "question"):
            return

        done = []
        if not self.generate():                                    # 1. labels
            return
        done.append(f"Generated {sum(len(v) for v in self.labels_by_box.values())} labels")
        try:
            made = self._make_folders()                            # 2. folders
            done.append(f"Created {made} folders")
            paths = self._write_files()                            # 3. print list + files
            done.append(f"Saved print list: {paths[0].name}")
            self._open_file(paths[0])
        except OSError as e:
            self._finish(done, f"Stopped - file/folder error:\n{e}")
            return
        if use_db:                                                 # 4. database
            try:
                import label_db
                n = label_db.insert_rows(self._conn_str(), self._rows())
                self.saved_to_db = True
                done.append(f"Saved {n} rows to the database")
            except Exception as e:
                self._finish(done, "Database save FAILED, nothing was inserted. Labels and folders are kept; "
                                   f"fix the problem and click 'Save to database…' to retry this same batch.\n\n{e}")
                return
        self._finish(done)

    def _finish(self, done, error=None):
        text = "\n".join(f"✔ {d}" for d in done)
        self.status.set(" | ".join(done) + (" | ERROR" if error else ""))
        if error:
            messagebox.showerror("Run all", f"{text}\n\n✖ {error}")
        else:
            messagebox.showinfo("Run all", f"All done.\n\n{text}")

    @staticmethod
    def _open_file(path):
        try:
            os.startfile(path)  # Windows: opens in Notepad (or default app) so you can print
        except (AttributeError, OSError):
            pass

    # ------------------------------------------------------------------ database
    def _conn_str(self):
        """Fresh read of config.ini every time, so edits apply without restarting."""
        return cfg.load_connection_string(APP_DIR)

    def _show_conn(self):
        try:
            text = cfg.masked(self._conn_str())
        except ValueError as e:
            text = f"Not set up yet: {e}"
        self.conn_preview.config(text=text)

    def open_config(self):
        p = cfg.ensure_config(APP_DIR)
        try:
            os.startfile(str(p))
        except (AttributeError, OSError):
            messagebox.showinfo("config.ini", f"Open this file in a text editor:\n\n{p}")

    def test_db(self):
        self._show_conn()
        try:
            import label_db
            label_db.existing_boxes(self._conn_str(), ["__test__"])
            messagebox.showinfo("Database", "Connection OK.")
        except Exception as e:
            messagebox.showerror("Database", f"Connection failed:\n\n{e}{self._drivers_hint()}")

    @staticmethod
    def _drivers_hint():
        try:
            import pyodbc
            drivers = [d for d in pyodbc.drivers() if "SQL Server" in d]
            return "\n\nSQL Server drivers on this PC:\n  " + ("\n  ".join(drivers) if drivers else "(none - install 'ODBC Driver 17 for SQL Server')")
        except ImportError:
            return "\n\npyodbc is not installed:  pip install pyodbc"

    def save_to_db(self):
        if not self._need_labels():
            return
        if self.saved_to_db:
            messagebox.showwarning("Already saved", "This batch was already saved. Generate a new batch first.")
            return
        try:
            import label_db
            conn = self._conn_str()
            existing = label_db.existing_boxes(conn, list(self.labels_by_box))
            rows = self._rows()
            msg = f"Insert {len(rows)} rows into dbo.InventoryPartSale?"
            if existing:
                listing = "\n".join(f"  {b}: {n} rows" for b, n in existing.items())
                msg += f"\n\nWARNING - these boxes already have rows:\n{listing}"
            if not messagebox.askyesno("Save to database", msg, icon="warning" if existing else "question"):
                return
            n = label_db.insert_rows(conn, rows)
        except Exception as e:
            messagebox.showerror("Database", f"Nothing was saved.\n\n{e}")
            return
        self.saved_to_db = True
        self.status.set(f"Saved {n} rows to the database.")
        messagebox.showinfo("Database", f"Saved {n} rows.")

    # ------------------------------------------------------------------ helpers
    @staticmethod
    def _set_text(widget, text):
        widget.delete("1.0", "end")
        widget.insert("1.0", text)

    def _load_settings(self):
        try:
            return json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}

    def _on_close(self):
        try:
            SETTINGS_FILE.write_text(json.dumps({k: v.get() for k, v in self.vars.items()}, indent=2), encoding="utf-8")
        except OSError:
            pass
        self.destroy()


# ---------------------------------------------------------------------- self-test (no window)
def self_test(check_db: bool = False) -> int:
    """
    Run without the window:   LabelGenerator.exe --selftest   (add --check-db to test the database too)
    Checks label generation, print list, folder creation, DB rows, config.ini and pyodbc.
    Writes the result to selftest.log next to the app. Exit code 0 = passed, 1 = failed.
    """
    import re
    import tempfile
    import traceback

    log: list[str] = [f"Label Generator self-test  {datetime.now():%Y-%m-%d %H:%M:%S}", f"App folder: {APP_DIR}"]
    failed = 0

    def check(name, fn):
        nonlocal failed
        try:
            detail = fn()
            log.append(f"PASS  {name}" + (f"  - {detail}" if detail else ""))
        except Exception as e:  # noqa: BLE001 - report every failure
            failed += 1
            log.append(f"FAIL  {name}  - {e}")
            log.append("      " + traceback.format_exc().strip().replace("\n", "\n      "))

    state: dict = {}

    def gen():
        boxes = core.box_range("BX0099", count=3)
        assert boxes == ["BX0099", "BX0100", "BX0101"], boxes
        state["lb"] = core.generate_labels(boxes, 28)
        labels = [l.text for v in state["lb"].values() for l in v]
        assert len(labels) == 84 and len(set(labels)) == 84
        bad = [t for t in labels if not re.fullmatch(r"\d{1,3}\.[0-9A-F]{5}-BX\d{4}", t)]
        assert not bad, bad[:3]
        return f"{len(labels)} labels, e.g. {labels[0]}"

    def print_list():
        lines = core.labels_text(state["lb"]).splitlines()
        assert lines[0] == core.LIST_HEADER[0]
        assert lines.count(core.BOX_SEPARATOR[0]) == 3
        assert len(lines) == 1 + 84 + 3 * len(core.BOX_SEPARATOR)
        return f"{len(lines)} lines"

    def folders():
        with tempfile.TemporaryDirectory() as tmp:
            for box, step, label in core.folder_paths(state["lb"], "1"):
                Path(tmp, box, step, label).mkdir(parents=True)
            n = sum(1 for p in Path(tmp).glob("*/*/*") if p.is_dir())
        assert n == 84, n
        return "84 folders created and removed in a temp folder"

    def rows():
        r = core.db_rows(state["lb"], "LabelsSum", "")
        assert len(r) == 84 and len(r[0]) == len(core.DB_COLUMNS)
        assert r[0][1] == r[0][7] and r[0][8] == "BX0099"
        return f"{len(r)} rows x {len(core.DB_COLUMNS)} columns"

    def config():
        state["conn"] = cfg.load_connection_string(APP_DIR)
        return cfg.masked(state["conn"])

    def driver():
        import pyodbc
        drivers = [d for d in pyodbc.drivers() if "SQL Server" in d]
        return f"pyodbc {pyodbc.version}; drivers: {', '.join(drivers) or 'NONE'}"

    def database():
        import label_db
        label_db.existing_boxes(state["conn"], ["__selftest__"])
        return "connected, read-only query OK (nothing written)"

    check("Generate labels", gen)
    if "lb" in state:
        check("Print list format", print_list)
        check("Create folders", folders)
        check("Database rows", rows)
    check("config.ini", config)
    check("pyodbc", driver)
    if check_db:
        if "conn" in state:
            check("Database connection", database)
        else:
            failed += 1
            log.append("FAIL  Database connection  - skipped, config.ini is not valid")

    log.append(f"RESULT: {'PASSED' if not failed else f'FAILED ({failed})'}")
    text = "\n".join(log) + "\n"
    try:
        (APP_DIR / "selftest.log").write_text(text, encoding="utf-8")
    except OSError:
        pass
    try:
        print(text)
    except Exception:  # windowed .exe has no console
        pass
    return 0 if not failed else 1


if __name__ == "__main__":
    if "--selftest" in sys.argv or "--check-db" in sys.argv:
        sys.exit(self_test(check_db="--check-db" in sys.argv))
    LabelApp().mainloop()
