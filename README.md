# Label Generator

Desktop app (Python + Tkinter) that generates eBay roll labels for a range of boxes.
It is a Python version of the stored procedure
`usp_GenerateInvPartGuidDB_et4500_EbayRollLabelsDynamic_NoAccount`, extended to a box range.

Label format: `<seq>.<GUID5>-<BOX>`, e.g. `6.26F40-BX3718`

## What it does
1. Generates labels for every box from **Start box** to **End box** (e.g. BX3718 – BX3738), N labels per box.
2. Creates the folders `...\0_staging\<Account>\<BOX>\<step>\<label>` in Dropbox.
3. Saves the print list (`labels_*.txt`) to the **Labels list folder** and can print it.
4. Inserts the rows into `dbo.InventoryPartSale` (one transaction).

**Run all** does all four steps; each step also has its own button.

## Setup
```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
copy config.example.ini config.ini     # then fill in server / username / password
.\.venv\Scripts\python.exe label_app.py
```
`config.ini` holds the database password and is **not** committed (see `.gitignore`).

## Tests and build
| Command | What it does |
|---|---|
| `run_tests.bat` | Runs the unit tests |
| `build_exe.bat` | Full rebuild: venv, packages, tests, `dist\LabelGenerator.exe`, self-test of the .exe, database check |
| `LabelGenerator.exe --selftest` | Checks the app without opening the window (`--check-db` also tests the database); result in `selftest.log` |

The built `.exe` reads `config.ini` from its own folder.

## Structure
Layers only depend on the layers below them; the window is a thin shell over testable code.

```
label_app.py                 launcher (PyCharm, run_label_app.bat, PyInstaller)
labelgen/
  main.py                    entry point: window, or --selftest / --check-db
  container.py               composition root: builds and wires all objects
  selftest.py                self-test without the window
  domain/                    no I/O
    boxes.py                 BoxId, BoxRange (BX3718..BX3738, zero padding, limits)
    models.py                Label, LabelBatch
    guid.py                  GUID5 code providers
    generator.py             LabelGenerator
    locations.py             staging folder rule
  formatting/                batch -> text
    print_list.py            roll print list (spacer lines)
    folder_script.py         mkdir .bat
    db_rows.py               InventoryPartSale rows + CSV
  infrastructure/            outside world
    config.py                config.ini -> connection string
    repository.py            SQL Server (pyodbc) + in-memory repository
    filesystem.py            label folders, batch files
    shell.py                 open / print files (Windows)
    settings.py              remembered form values
  services/
    job.py                   JobSettings: validated form values
    label_service.py         LabelService: everything the app can do
    pipeline.py              Run all as steps
  ui/
    controller.py            all button logic (no tkinter)
    view.py                  what the controller needs from a window
    tk_view.py               the Tkinter window
    theme.py                 colours and fonts
    defaults.py              first-run form values
tests/                       unit tests per layer (unittest)
```

### Design patterns
| Pattern | Where | Why |
|---|---|---|
| **Layered architecture** | `domain` → `formatting` → `infrastructure` → `services` → `ui` | Rules don't depend on Tkinter, SQL Server or disk |
| **Model-View-Presenter** | `ui/controller.py` + `ui/tk_view.py` | Button logic is tested without opening a window |
| **Facade** | `LabelService` | One simple API for the UI and the self-test |
| **Repository** | `LabelRepository` → `SqlServerLabelRepository`, `InMemoryLabelRepository` | Database access in one place; tests run without SQL Server |
| **Strategy** | `GuidProvider`, `BatchFormatter` subclasses | Swap GUID source (fixed codes in tests); add output formats without touching the rest |
| **Command / Pipeline** | `services/pipeline.py` steps | Run all = ordered steps, stops at the first failure with a clear message |
| **Observer** | `ProgressListener` | Status bar follows each Run all step |
| **Adapter** | `WindowsShell` | Wraps `os.startfile` for open / print |
| **Factory / dependency injection** | `container.py` | The only place that picks concrete classes |
| **Value objects** | `BoxId`, `BoxRange`, `Label`, `JobSettings` | Validated, immutable inputs |

### Common changes
| To change… | Edit |
|---|---|
| Print list spacer lines | `labelgen/formatting/print_list.py` |
| Database columns / values | `labelgen/formatting/db_rows.py` |
| Staging folder path | `labelgen/domain/locations.py` |
| First-run form values | `labelgen/ui/defaults.py` |
| Colours and fonts | `labelgen/ui/theme.py` |
| Run all steps | `build_run_all_pipeline` in `labelgen/services/pipeline.py` |
