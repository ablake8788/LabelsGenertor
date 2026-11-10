"""Minimal stand-in for tkinter so the app logic can be tested without opening a window."""
import sys
import types

LOG = []          # every dialog shown: (kind, title, message)
ANSWER = [True]   # what askyesno returns


class Var:
    def __init__(self, value=""):
        self._v = value

    def get(self):
        return self._v

    def set(self, v):
        self._v = v

    def trace_add(self, *a):
        pass


def install():
    tk = types.ModuleType("tkinter")
    tk.Tk = type("Tk", (), {})
    tk.StringVar = Var
    tk.Text = object
    mb = types.ModuleType("tkinter.messagebox")
    mb.showerror = lambda t, m, **k: LOG.append(("error", t, m))
    mb.showinfo = lambda t, m, **k: LOG.append(("info", t, m))
    mb.showwarning = lambda t, m, **k: LOG.append(("warning", t, m))
    mb.askyesno = lambda t, m, **k: (LOG.append(("ask", t, m)), ANSWER[0])[1]
    fd = types.ModuleType("tkinter.filedialog")
    ttk = types.ModuleType("tkinter.ttk")
    tk.messagebox, tk.filedialog, tk.ttk = mb, fd, ttk
    sys.modules.update({"tkinter": tk, "tkinter.messagebox": mb, "tkinter.filedialog": fd, "tkinter.ttk": ttk})
