# Standalone Scripts

Two approaches exist for running Python scripts that use QGIS outside of the QGIS application itself.
This page explains both, shows how they map to each other, and covers the Windows-specific DLL
loading subtleties that make the self-configuring approach non-trivial.

---

## Option 1 — platform launcher (`python-qgis.bat`)

QGIS ships a small launcher on each platform that sets up the environment and then runs the
bundled Python interpreter. Use this when you want the simplest possible setup and are happy
to invoke the script through the launcher.

=== "Windows"

    ```bat
    "C:\Program Files\QGIS 3.28.0\bin\python-qgis.bat" my_script.py
    ```

=== "macOS"

    Open a terminal through `/Applications/QGIS.app` (e.g. via `open -a QGIS` and use the
    embedded Python) or use the OSGeo4Mac shell wrapper if installed.

=== "Linux"

    ```bash
    python my_script.py   # system Python works if QGIS was installed system-wide
    ```

Your script only needs to call `QgsApplication.setPrefixPath()` — the rest of the environment
is already in place:

```python
from qgis.core import *

QgsApplication.setPrefixPath(find_qgis_prefix_path(), True)
qgs = QgsApplication([], False)
qgs.initQgis()
```

### What the bat does (Windows)

`python-qgis.bat` is a thin wrapper that chains several setup scripts and then runs the QGIS-bundled Python.
The call sequence is:

```
python-qgis.bat
└── o4w_env.bat                       # sets OSGEO4W_ROOT, resets PATH, runs etc/ini/*.bat
    ├── qt5.bat                       # PATH += apps\qt5\bin; QT_PLUGIN_PATH
    ├── python3.bat                   # PYTHONHOME = apps\Python39; PATH += apps\Python39\Scripts
    └── gdal.bat / proj-runtime-data.bat / …
```

Then `python-qgis.bat` itself adds the final layer:

```bat
path %OSGEO4W_ROOT%\apps\qgis\bin;%PATH%
set QGIS_PREFIX_PATH=%OSGEO4W_ROOT:\=/%/apps/qgis
set GDAL_FILENAME_IS_UTF8=YES
set VSI_CACHE=TRUE
set VSI_CACHE_SIZE=1000000
set QT_PLUGIN_PATH=%OSGEO4W_ROOT%\apps\qgis\qtplugins;%OSGEO4W_ROOT%\apps\qt5\plugins
set PYTHONPATH=%OSGEO4W_ROOT%\apps\qgis\python;%PYTHONPATH%
python %*
```

The net result — directories on `PATH` and the Python environment that is launched:

| What                         | Value (QGIS 3.28 default)                                    |
|------------------------------|--------------------------------------------------------------|
| `PATH` additions             | `…\bin`, `…\apps\qt5\bin`, `…\apps\qgis\bin`                |
| `PYTHONPATH`                 | `…\apps\qgis\python`                                         |
| `PYTHONHOME`                 | `…\apps\Python39`                                            |
| `QGIS_PREFIX_PATH`           | `.../apps/qgis`                                              |
| `QT_PLUGIN_PATH`             | `…\apps\qgis\qtplugins;…\apps\qt5\plugins`                  |
| `GDAL_FILENAME_IS_UTF8`      | `YES`                                                        |
| `VSI_CACHE` / `VSI_CACHE_SIZE` | `TRUE` / `1000000`                                         |
| Python interpreter           | `…\bin\python.exe` (QGIS-bundled, Python 3.9 for QGIS 3.28) |

---

## Option 2 — `setup_local_python()` (self-configuring)

`setup_local_python()` (in [`experiments/utils.py`](../experiments/utils.py)) replicates the
bat's work from inside Python, so the script can be launched with **any compatible Python
interpreter** — no wrapper needed.

```python
# docs_auto.py — run with: python docs_auto.py
from utils import find_qgis_prefix_path, setup_local_python

setup_local_python()          # must come before any qgis import

from qgis.core import *
QgsApplication.setPrefixPath(find_qgis_prefix_path(), True)
qgs = QgsApplication([], False)
qgs.initQgis()
```

### Step-by-step comparison (Windows)

| Step | `python-qgis.bat` | `setup_local_python()` |
|---|---|---|
| **Find install root** | `OSGEO4W_ROOT` set by `o4w_env.bat` from the bat's own location | `find_qgis_prefix_path()` searches `QGIS_PREFIX_PATH` env var → `CONDA_PREFIX` (validated) → `Program Files\QGIS*` |
| **Python bindings on path** | `PYTHONPATH` env var (effective for the child process) | `sys.path.insert(0, prefix/python)` (modifies the running interpreter) |
| **Qt5 DLLs** | `apps\qt5\bin` prepended to `PATH` before the process starts | `os.add_dll_directory(root/apps/Qt5/bin)` + ctypes pre-load |
| **QGIS DLLs** | `apps\qgis\bin` prepended to `PATH` before the process starts | `os.add_dll_directory(prefix/bin)` + ctypes pre-load |
| **GDAL DLLs** | `bin\` on `PATH` (set by `o4w_env.bat`) | `os.add_dll_directory(root/bin)` + ctypes pre-load of `gdal*.dll` |
| **`PYTHONHOME`** | Set to `apps\Python39` — tells the bundled Python where its stdlib is | **Not set** — the external Python already knows its own stdlib |
| **Env vars** | Set by `python-qgis.bat` for the child process | `os.environ.setdefault(...)` on the running process |

### Why `PYTHONHOME` is intentionally skipped

The bat sets `PYTHONHOME` because it is launching the QGIS-bundled Python, which needs to be
told where its standard library lives. When running with an external interpreter (conda, system
Python), `PYTHONHOME` is already correct for that interpreter. Setting it to the QGIS Python
path would break stdlib imports in your own code.

### Why DLLs must be pre-loaded (Windows)

`os.add_dll_directory()` enlarges the search path used by Python's import machinery when it
loads a `.pyd` file. It does **not** reliably affect `LoadLibrary` calls made *from within*
that `.pyd` file — i.e. transitive dependencies.

`_core.pyd` links against `qgis_core.dll`, which links against Qt5 and GDAL DLLs. Because
those loads happen inside the C extension (not through Python), `add_dll_directory` alone is
insufficient. Pre-loading the DLLs with `ctypes.CDLL` puts them into the Windows
process's loaded-module table so any subsequent `LoadLibrary` for the same name gets the
already-loaded handle — no filesystem search needed.

Load order matters (dependencies before dependents):

```
Qt5Core.dll  →  gdal*.dll  →  qgis_core.dll  →  qgis/_core.pyd
```

### Platform summary

| Platform | Env mechanism | DLL/SO mechanism | `setup_local_python()` equivalent |
|---|---|---|---|
| **Windows** | `PATH` + `PYTHONPATH` via bat | `os.add_dll_directory` + ctypes pre-load | `_setup_windows()` |
| **macOS** | Shell wrapper / QGIS.app env | `DYLD_LIBRARY_PATH` | `_setup_macos()` |
| **Linux** | Shell wrapper or system install | `LD_LIBRARY_PATH` | `_setup_linux()` |

---

## Python version constraint

The QGIS Python bindings (`.pyd` / `.so` files) are compiled for a specific CPython version.
A standalone QGIS 3.28 installer bundles **Python 3.9**; the bindings cannot be loaded by
Python 3.10 or any other version.

`setup_local_python()` detects this mismatch early and raises a clear error:

```
RuntimeError: Python version mismatch: QGIS bundles Python39 but you are running Python310.
Use python-qgis.bat (docs.py) or install QGIS via conda into an env with Python 3.9.
```

To avoid this constraint entirely, install QGIS via conda-forge into an environment — conda
will always install bindings compiled for that environment's Python version:

```bash
conda create -n qgis python=3.12 qgis -c conda-forge
```
