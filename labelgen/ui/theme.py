"""
Look and feel for the Tk window: a 'workshop' palette (slate, steel grey, safety amber)
applied to ttk's 'clam' theme. Colours and fonts live here only.
"""
from __future__ import annotations

import tkinter as tk
from tkinter import font as tkfont
from tkinter import ttk

# ---------------------------------------------------------------------- palette
SLATE = "#25313B"        # header band
SLATE_TEXT = "#E8EDF1"   # text on the header
SLATE_MUTED = "#9AA8B4"
WORKSPACE = "#E6EAEE"    # window background
SURFACE = "#FFFFFF"      # panels, inputs
INK = "#1F2933"          # main text
MUTED = "#616E7C"        # secondary text
BORDER = "#C5CDD5"
BORDER_STRONG = "#9AA5B1"
AMBER = "#F2B705"        # safety amber - only the main action
AMBER_HOVER = "#DDA603"
AMBER_PRESSED = "#C79502"
FOCUS = "#3E7CB1"
OK = "#2F7D4A"
OK_BG = "#E3F1E7"
WARN = "#9A6700"
WARN_BG = "#FFF4D6"
ERROR = "#B42318"
ERROR_BG = "#FDE7E5"
IDLE_BG = "#EEF1F4"

# label roll preview
ROLL_LINER = "#CBD3DB"   # backing strip
ROLL_LABEL = "#FFFFFF"   # sticker
ROLL_INK = "#111820"
ROLL_SEPARATOR = "#6B7884"

ROW_ALT = "#F4F6F8"


def pick_font(root: tk.Misc, *families: str) -> str:
    available = set(tkfont.families(root))
    return next((f for f in families if f in available), "TkDefaultFont")


class Fonts:
    def __init__(self, root: tk.Misc):
        ui = pick_font(root, "Segoe UI", "Helvetica Neue", "DejaVu Sans")
        semibold = pick_font(root, "Segoe UI Semibold", "Segoe UI", "DejaVu Sans")
        mono = pick_font(root, "Cascadia Mono", "Consolas", "DejaVu Sans Mono", "Courier New")
        self.body = (ui, 10)
        self.small = (ui, 9)
        self.section = (semibold, 11)
        self.title = (semibold, 15)
        self.button = (ui, 10)
        self.primary = (semibold, 11)
        self.figure = (semibold, 18)
        self.mono = (mono, 11)
        self.mono_bold = (mono, 11, "bold")


def apply_theme(root: tk.Tk) -> Fonts:
    f = Fonts(root)
    root.configure(bg=WORKSPACE)
    root.option_add("*Font", f.body)
    s = ttk.Style(root)
    s.theme_use("clam")

    s.configure(".", background=WORKSPACE, foreground=INK, font=f.body, bordercolor=BORDER,
                lightcolor=SURFACE, darkcolor=BORDER, troughcolor=WORKSPACE, focuscolor=FOCUS)

    # frames and text
    s.configure("TFrame", background=WORKSPACE)
    s.configure("Panel.TFrame", background=SURFACE)
    s.configure("Header.TFrame", background=SLATE)
    s.configure("TLabel", background=WORKSPACE, foreground=INK)
    s.configure("Panel.TLabel", background=SURFACE, foreground=INK)
    s.configure("Muted.Panel.TLabel", background=SURFACE, foreground=MUTED, font=f.small)
    s.configure("Path.Panel.TLabel", background=SURFACE, foreground=MUTED, font=f.small)
    s.configure("Section.Panel.TLabel", background=SURFACE, foreground=INK, font=f.section)
    s.configure("Title.Header.TLabel", background=SLATE, foreground=SLATE_TEXT, font=f.title)
    s.configure("Sub.Header.TLabel", background=SLATE, foreground=SLATE_MUTED, font=f.small)
    s.configure("Figure.TLabel", background=WORKSPACE, foreground=INK, font=f.figure)
    s.configure("FigureCaption.TLabel", background=WORKSPACE, foreground=MUTED, font=f.small)
    s.configure("Status.TLabel", background=SURFACE, foreground=MUTED, font=f.small, padding=(12, 6))
    s.configure("TSeparator", background=BORDER)

    # inputs
    for widget in ("TEntry", "TSpinbox"):
        s.configure(widget, fieldbackground=SURFACE, foreground=INK, bordercolor=BORDER,
                    lightcolor=SURFACE, darkcolor=SURFACE, padding=(6, 4), insertcolor=INK)
        s.map(widget, bordercolor=[("focus", FOCUS)], lightcolor=[("focus", FOCUS)])
    s.configure("TSpinbox", arrowsize=12, arrowcolor=MUTED, background=SURFACE)
    s.configure("TCheckbutton", background=SURFACE, foreground=INK, focuscolor=SURFACE, indicatorcolor=SURFACE)
    s.map("TCheckbutton", indicatorcolor=[("selected", AMBER)], background=[("active", SURFACE)])

    # buttons
    s.configure("TButton", background=SURFACE, foreground=INK, bordercolor=BORDER, lightcolor=SURFACE,
                darkcolor=SURFACE, padding=(10, 5), font=f.button, focusthickness=1)
    s.map("TButton", background=[("pressed", "#DCE2E8"), ("active", "#F0F3F6")],
          bordercolor=[("active", BORDER_STRONG), ("focus", FOCUS)])
    s.configure("Primary.TButton", background=AMBER, foreground=INK, bordercolor=AMBER_PRESSED,
                lightcolor=AMBER, darkcolor=AMBER, padding=(14, 9), font=f.primary)
    s.map("Primary.TButton", background=[("pressed", AMBER_PRESSED), ("active", AMBER_HOVER)],
          lightcolor=[("active", AMBER_HOVER)], darkcolor=[("active", AMBER_HOVER)])
    s.configure("Quiet.TButton", background=SURFACE, foreground=MUTED, bordercolor=SURFACE,
                lightcolor=SURFACE, darkcolor=SURFACE, padding=(6, 4), font=f.small)
    s.map("Quiet.TButton", foreground=[("active", INK)], background=[("active", "#F0F3F6")])
    s.configure("Browse.TButton", padding=(8, 3), font=f.small)

    # tabs
    s.configure("TNotebook", background=WORKSPACE, borderwidth=0, tabmargins=(0, 0, 0, 0))
    s.configure("TNotebook.Tab", background=WORKSPACE, foreground=MUTED, padding=(14, 7), borderwidth=0,
                lightcolor=WORKSPACE, bordercolor=WORKSPACE)
    s.map("TNotebook.Tab", background=[("selected", SURFACE)], foreground=[("selected", INK)],
          lightcolor=[("selected", SURFACE)], bordercolor=[("selected", BORDER)])

    # table
    s.configure("Treeview", background=SURFACE, fieldbackground=SURFACE, foreground=INK, rowheight=24,
                bordercolor=BORDER, lightcolor=SURFACE, darkcolor=SURFACE)
    s.map("Treeview", background=[("selected", "#D6E4F0")], foreground=[("selected", INK)])
    s.configure("Treeview.Heading", background=IDLE_BG, foreground=INK, font=f.small, relief="flat",
                bordercolor=BORDER, padding=(6, 5))
    s.map("Treeview.Heading", background=[("active", "#E2E7EC")])

    s.configure("Vertical.TScrollbar", background=IDLE_BG, troughcolor=SURFACE, bordercolor=SURFACE,
                arrowcolor=MUTED, lightcolor=IDLE_BG, darkcolor=IDLE_BG)
    s.configure("Horizontal.TScrollbar", background=IDLE_BG, troughcolor=SURFACE, bordercolor=SURFACE,
                arrowcolor=MUTED, lightcolor=IDLE_BG, darkcolor=IDLE_BG)
    return f
