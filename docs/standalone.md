# How qgis-project connects to QGIS

QGIS has a powerful Python API (PyQGIS — `qgis.core`, `qgis.gui`, `processing`,
…), but it is **not available on PyPI**. The
bindings are compiled C++ extensions that live *inside* a QGIS installation and
are tied to the exact Python version, Qt version, and GDAL/PROJ libraries that
install was built against.

`qgis-project` itself is pure Python with no runtime dependencies; all the
real work happens in PyQGIS. So before anything runs, you need a way to reach
those bindings. There are three ways to do that. The package supports all three
and picks one automatically (see [Launch modes](#launch-modes-forcing-the-choice)).
This page explains each one in plain language — what it does, when to use it, and
how it works under the hood.

!!! tip "The short version"
    Two of these are the recommended setups:

    - **A — Subprocess wrapper** (`local`): you already have the QGIS desktop app;
      keep your own lightweight Python env and let the package run the work
      through QGIS's bundled Python. No `qgis` conda package needed.
    - **B — conda-forge** (`env`): install `qgis` from conda-forge into a conda
      environment and run everything in that interpreter.

    The third (manual in-process with a standalone install) is fragile and only
    for advanced cases.

---

## The three approaches

### A — Subprocess execution wrapper

*Recommended if you already use the QGIS desktop app.* &nbsp; → Strategy 2,
mode `local`

You install QGIS the normal way (the desktop app from qgis.org, or OSGeo4W on
Windows). That install ships its own private Python with PyQGIS already wired up.
Instead of importing PyQGIS into *your* interpreter, the package serializes a
small description of your project to a temporary file and hands it to QGIS's
bundled Python through the platform launcher (`python-qgis.bat` on Windows,
`python-qgis.sh` elsewhere), which runs it in a child process.

**Why it's nice.** Your own environment stays tiny — just `qgis-project`
itself. You never install the heavy `qgis` conda package, and you never hit
Python/Qt/GDAL version conflicts, because the code executes inside the exact
environment QGIS shipped. One QGIS install on the machine is enough.

**The trade-off.** It is a little "hacky": data crosses a process boundary as a
serialized spec, and because execution happens in a separate process there are no
live QGIS objects to inspect — `snapshot()` and other live-canvas features are
unavailable.

Ready-made env: [`environments/strategy2-wrapper.yml`](https://github.com/ColinMoldenhauer/qgis-project/blob/main/environments/strategy2-wrapper.yml).

### B — QGIS from conda-forge (in-process)

*Recommended for interactive / notebook use.* &nbsp; → Strategy 3, mode `env`

You create a conda environment and install `qgis` from the conda-forge channel
alongside your own packages. conda-forge builds the bindings against that
environment's exact Python, so a plain `import qgis` just works. The package then
runs everything in your interpreter, in-process, with full access to live QGIS
objects.

**Why it's nice.** Clean and conventional — no subprocess, no launcher, no DLL
juggling. Live objects are available.

**The trade-off.** The environment is large (`qgis` pulls in Qt, GDAL, PROJ,
etc. — easily over 1 GB), and if you also have the desktop app you now keep two
copies of the QGIS stack on disk. The conda-forge QGIS version is independent of
any desktop install.

Ready-made env: [`environments/strategy3-conda.yml`](https://github.com/ColinMoldenhauer/qgis-project/blob/main/environments/strategy3-conda.yml).

### C — Manual in-process setup with a standalone install

*Advanced and fragile — prefer A or B.* &nbsp; → Strategy 1, mode `env`

This reaches into an existing QGIS desktop install and imports its bindings
directly into *your* interpreter — no subprocess, no conda `qgis`. The package
replicates what the launcher does (puts the bindings on `sys.path`, registers DLL
directories, and pre-loads the native libraries) so that `import qgis` succeeds in
your process.

**Why it's tempting.** A single QGIS install (like A) but with live in-process
objects (like B).

**Why it's fragile.** Your interpreter's Python version must match the
standalone's bundled Python **exactly** — the bindings are ABI-locked, so a build
for Python 3.9 cannot load under 3.12. On top of that, any conflicting package in
your environment (a newer NumPy, a second Qt) can crash the bindings at import.
This is the classic "dependency hell" path. When the Python versions don't match,
the package detects it and automatically falls back to approach A if a launcher is
available.

Ready-made env: [`environments/strategy1-standalone.yml`](https://github.com/ColinMoldenhauer/qgis-project/blob/main/environments/strategy1-standalone.yml).

---

## At a glance

|                              | A — Subprocess wrapper | B — conda-forge      | C — Manual in-process |
|------------------------------|------------------------|----------------------|-----------------------|
| Strategy / mode              | 2 / `local`            | 3 / `env`            | 1 / `env`             |
| Needs QGIS desktop install   | ✅ yes                 | no                   | ✅ yes                |
| Needs `qgis` from conda      | no                     | ✅ yes               | no                    |
| Your Python env              | tiny (no deps)         | large (QGIS stack)   | tiny, version-locked  |
| Code runs in                 | QGIS bundled Python (subprocess) | your interpreter | your interpreter |
| Live QGIS objects            | no                     | ✅ yes               | ✅ yes                |
| Main risk                    | none (process-isolated)| disk size, duplicate stacks | version/ABI conflicts |
| Verdict                      | ✅ recommended         | ✅ recommended       | ⚠️ advanced           |

---

## Launch modes (forcing the choice)

By default `qgis_project` auto-picks: it uses the QGIS bindings importable in the
current environment (in-process, approach B or C) when available, otherwise it
falls back to a standalone install driven through the launcher (approach A).
Override this with the `QGIS_PROJECT_LAUNCH_MODE` environment variable or at
runtime via `set_mode()`:

| Value     | Meaning                                                            |
|-----------|-------------------------------------------------------------------|
| `auto`    | Default — in-process if importable, else the standalone launcher. |
| `env`     | Force the QGIS bindings in the current Python env (in-process).    |
| `local`   | Force a standalone/local QGIS install (subprocess launcher).       |

```bash
# Ignore an importable `qgis` and drive the local standalone install instead:
export QGIS_PROJECT_LAUNCH_MODE=local   # Windows: set QGIS_PROJECT_LAUNCH_MODE=local
```

```python
import qgis_project
qgis_project.set_mode("local")      # same effect, at runtime, before Project()
```

Forcing a mode whose backend is unavailable raises immediately — `set_mode("env")`
without importable bindings raises `ImportError`; `set_mode("local")` without a
launcher raises `RuntimeError`. `set_mode()` must be called before constructing a
`Project`.

---

## Under the hood

The rest of this page covers the Windows-specific mechanics behind approaches A
and C — useful if you are debugging an install, but not required reading.

### Approach A — the platform launcher (`python-qgis.bat`)

QGIS ships a small launcher on each platform that sets up the environment and then
runs the bundled Python interpreter. Approach A simply invokes it:

=== "Windows"

    ```bat
    "C:\Program Files\QGIS 3.28.0\bin\python-qgis.bat" my_script.py
    ```

=== "macOS"

    Open a terminal through `/Applications/QGIS.app` (e.g. via `open -a QGIS` and
    use the embedded Python) or use the OSGeo4Mac shell wrapper if installed.

=== "Linux"

    ```bash
    python my_script.py   # system Python works if QGIS was installed system-wide
    ```

`python-qgis.bat` is a thin wrapper that chains several setup scripts and then runs
the QGIS-bundled Python. The call sequence is:

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

### Approach C — self-configuring in-process setup

`setup_qgis_env()` (in [`qgis_project/_env.py`](https://github.com/ColinMoldenhauer/qgis-project/blob/main/src/qgis_project/_env.py))
replicates the launcher's work from inside Python, so the bindings can be imported
by an external interpreter — no wrapper needed. It runs automatically the first
time you construct a `Project` in `env` mode. The table below shows how it maps to
the bat, step by step (Windows):

| Step | `python-qgis.bat` (approach A) | `setup_qgis_env()` (approach C) |
|---|---|---|
| **Find install root** | `OSGEO4W_ROOT` set by `o4w_env.bat` from the bat's own location | `find_qgis_prefix_path()` searches `QGIS_PREFIX_PATH` env var → `CONDA_PREFIX` (validated) → `Program Files\QGIS*` |
| **Python bindings on path** | `PYTHONPATH` env var (effective for the child process) | `sys.path.insert(0, prefix/python)` (modifies the running interpreter) |
| **Qt5 DLLs** | `apps\qt5\bin` prepended to `PATH` before the process starts | `os.add_dll_directory(root/apps/Qt5/bin)` + ctypes pre-load |
| **QGIS DLLs** | `apps\qgis\bin` prepended to `PATH` before the process starts | `os.add_dll_directory(prefix/bin)` + ctypes pre-load |
| **GDAL DLLs** | `bin\` on `PATH` (set by `o4w_env.bat`) | `os.add_dll_directory(root/bin)` + ctypes pre-load of `gdal*.dll` |
| **`PYTHONHOME`** | Set to `apps\Python39` — tells the bundled Python where its stdlib is | **Not set** — the external Python already knows its own stdlib |
| **Env vars** | Set by `python-qgis.bat` for the child process | `os.environ.setdefault(...)` on the running process |

#### Why `PYTHONHOME` is intentionally skipped

The bat sets `PYTHONHOME` because it is launching the QGIS-bundled Python, which
needs to be told where its standard library lives. When running with an external
interpreter (conda, system Python), `PYTHONHOME` is already correct for that
interpreter. Setting it to the QGIS Python path would break stdlib imports in your
own code.

#### Why DLLs must be pre-loaded (Windows)

`os.add_dll_directory()` enlarges the search path used by Python's import machinery
when it loads a `.pyd` file. It does **not** reliably affect `LoadLibrary` calls
made *from within* that `.pyd` file — i.e. transitive dependencies.

`_core.pyd` links against `qgis_core.dll`, which links against Qt5 and GDAL DLLs.
Because those loads happen inside the C extension (not through Python),
`add_dll_directory` alone is insufficient. Pre-loading the DLLs with `ctypes.CDLL`
puts them into the Windows process's loaded-module table so any subsequent
`LoadLibrary` for the same name gets the already-loaded handle — no filesystem
search needed.

Load order matters (dependencies before dependents):

```
Qt5Core.dll  →  gdal*.dll  →  qgis_core.dll  →  qgis/_core.pyd
```

### Platform summary

| Platform | Env mechanism | DLL/SO mechanism | `setup_qgis_env()` helper |
|---|---|---|---|
| **Windows** | `PATH` + `PYTHONPATH` via bat | `os.add_dll_directory` + ctypes pre-load | `_setup_windows()` |
| **macOS** | Shell wrapper / QGIS.app env | `DYLD_LIBRARY_PATH` | `_setup_macos()` |
| **Linux** | Shell wrapper or system install | `LD_LIBRARY_PATH` | `_setup_linux()` |

---

## Python version constraint (approach C)

The QGIS Python bindings (`.pyd` / `.so` files) are compiled for a specific CPython
version. A standalone QGIS 3.28 installer bundles **Python 3.9**; those bindings
cannot be loaded by Python 3.10 or any other version.

`setup_qgis_env()` detects this mismatch early. Rather than crash, it logs a
warning and skips the in-process path so the package can fall back to the
subprocess launcher (approach A) if one is available:

```
Python version mismatch: QGIS bundles Python39 but you are running Python310.
In-process QGIS (Strategy 1) will not be available; falling back to subprocess
launcher (Strategy 2) if found.
```

To avoid this constraint entirely, install QGIS via conda-forge (approach B) —
conda always installs bindings compiled for that environment's Python version:

```bash
conda create -n qgis python=3.12 qgis -c conda-forge
```
