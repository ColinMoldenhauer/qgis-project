"""
Environment setup for QGIS — no qgis imports allowed in this module.

This module must be importable *before* QGIS is on sys.path, which is why it
contains no `from qgis` imports. It is the first thing __init__.py imports so
that subsequent modules with module-level qgis imports can succeed.
"""

import logging
import os
import platform
import shutil
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

# os.add_dll_directory() returns a handle that must stay alive to keep the
# directory on the search path. Store handles here to prevent GC.
_dll_directory_handles: list = []


def find_qgis_prefix_path() -> str:
    """Return the QGIS prefix path for `QgsApplication.setPrefixPath()`.

    Resolution order:

    1. `QGIS_PREFIX_PATH` env var — explicit override, always wins.
    2. `CONDA_PREFIX` env var — only used when QGIS bindings are actually
       present in that env (validated by checking the expected bindings path).
    3. Platform-specific default install locations (standalone installers).

    Raises `RuntimeError` if no installation can be found.
    """
    logger.debug("Resolving QGIS prefix path...")

    if path := os.environ.get("QGIS_PREFIX_PATH"):
        logger.debug(f"QGIS_PREFIX_PATH override set; using prefix: {path}")
        return path

    system = platform.system()
    logger.debug(f"No QGIS_PREFIX_PATH override; detecting on platform '{system}'.")

    if conda_prefix := os.environ.get("CONDA_PREFIX"):
        logger.debug(f"CONDA_PREFIX is set: {conda_prefix}")
        if system == "Windows":
            candidate = Path(conda_prefix) / "Library"
            if (candidate / "python").exists():
                logger.debug(f"conda bindings found; using prefix: {candidate}")
                return str(candidate)
            logger.debug(f"conda bindings not present at {candidate / 'python'}; skipping conda.")
        else:
            candidate = Path(conda_prefix)
            if (candidate / "share" / "qgis" / "python").exists():
                logger.debug(f"conda bindings found; using prefix: {candidate}")
                return str(candidate)
            logger.debug(
                f"conda bindings not present at "
                f"{candidate / 'share' / 'qgis' / 'python'}; skipping conda."
            )
    else:
        logger.debug("CONDA_PREFIX not set; skipping conda detection.")

    if system == "Windows":
        for base in [
            Path(os.environ.get("PROGRAMFILES", r"C:\Program Files")),
            Path(os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)")),
        ]:
            if not base.exists():
                logger.debug(f"Program Files base does not exist: {base}")
                continue
            install_dirs = sorted(base.glob("QGIS*"), reverse=True)
            logger.debug(f"Searching {base}: found {len(install_dirs)} QGIS* dir(s).")
            for candidate in install_dirs:
                apps_dir = candidate / "apps"
                # Try versioned names (e.g. apps/qgis, apps/qgis-ltr, apps/qgis4)
                for app_dir in sorted(apps_dir.glob("qgis*"), reverse=True):
                    if app_dir.is_dir():
                        logger.debug(f"Standalone QGIS prefix found: {app_dir}")
                        return str(app_dir)
            logger.debug(f"No usable apps/qgis* dir under any QGIS* in {base}.")
    elif system == "Darwin":
        for app in ["QGIS.app", "QGIS-LTR.app"]:
            prefix = Path("/Applications") / app / "Contents" / "MacOS"
            if prefix.exists():
                logger.debug(f"macOS QGIS prefix found: {prefix}")
                return str(prefix)
            logger.debug(f"macOS app bundle not present: {prefix}")
    else:
        qgis_bin = shutil.which("qgis")
        if qgis_bin:
            prefix = Path(qgis_bin).resolve().parent.parent
            logger.debug(f"qgis on PATH at {qgis_bin}; derived prefix: {prefix}")
            return str(prefix)
        logger.debug("qgis not found on PATH; checking standard system prefixes.")
        for prefix in [Path("/usr"), Path("/usr/local")]:
            if (prefix / "bin" / "qgis").exists():
                logger.debug(f"Linux QGIS prefix found: {prefix}")
                return str(prefix)
            logger.debug(f"No qgis binary at {prefix / 'bin' / 'qgis'}.")

    logger.error(f"QGIS installation could not be located on platform '{system}'.")
    raise RuntimeError(
        "Could not find a QGIS installation. "
        "Set the QGIS_PREFIX_PATH environment variable to the QGIS prefix directory."
    )


def find_qgis_launcher():
    """Return the path to the platform-specific QGIS Python launcher, or None.

    The launcher is the script that sets up the QGIS environment and then
    runs the bundled Python interpreter — `python-qgis.bat` on Windows,
    `python-qgis.sh` on Linux, and the macOS shell wrapper.  It is used
    by SubprocessProject to delegate execution to the QGIS Python.
    """
    system = platform.system()
    logger.debug(f"Locating QGIS Python launcher on platform '{system}'...")

    try:
        prefix = Path(find_qgis_prefix_path())
    except RuntimeError:
        logger.debug("No QGIS prefix found; cannot locate launcher.")
        return None

    if system == "Windows":
        # Standalone: prefix = <root>/apps/qgis  →  bat is in <root>/bin
        conda_prefix = os.environ.get("CONDA_PREFIX")
        is_conda = bool(conda_prefix and str(prefix).startswith(conda_prefix))
        root = prefix if is_conda else prefix.parent.parent
        logger.debug(f"Launcher search root (is_conda={is_conda}): {root / 'bin'}")
        for bat_name in ["python-qgis.bat", "python-qgis4.bat", "python3-qgis.bat"]:
            bat = root / "bin" / bat_name
            if bat.exists():
                logger.debug(f"QGIS launcher found: {bat}")
                return str(bat)
        logger.debug(f"No python-qgis*.bat launcher found in {root / 'bin'}.")
        return None

    if system == "Darwin":
        for name in ["python-qgis.sh", "python-qgis4.sh", "python3-qgis.sh"]:
            wrapper = prefix / "bin" / name
            if wrapper.exists():
                logger.debug(f"QGIS launcher found: {wrapper}")
                return str(wrapper)
        logger.debug(f"No python-qgis*.sh launcher found in {prefix / 'bin'}.")
        return None

    # Linux
    for name in ["python-qgis.sh", "python-qgis4.sh", "python3-qgis.sh"]:
        wrapper = prefix / "bin" / name
        if wrapper.exists():
            logger.debug(f"QGIS launcher found: {wrapper}")
            return str(wrapper)
    logger.debug(f"No python-qgis*.sh launcher found in {prefix / 'bin'}.")
    return None


def setup_qgis_env() -> bool:
    """Make the QGIS Python bindings importable by auto-configuring the environment.

    Handles three install scenarios transparently:

    - **conda-forge**: detects `CONDA_PREFIX` and adds the bindings path.
    - **Standalone installer** (Windows/macOS/Linux): locates the install,
      registers DLL directories, and pre-loads key native libraries.
    - **Already configured** (e.g. launched via `python-qgis.bat`): detects
      that `import qgis` already works and returns immediately.

    Returns `True` if `import qgis` succeeds after this call, `False` if
    QGIS could not be located.
    """
    system = platform.system()
    logger.debug(
        f"setup_qgis_env() starting on '{system}' "
        f"(python {sys.version_info.major}.{sys.version_info.minor})."
    )

    try:
        import qgis  # noqa: F401
        # qgis is already importable, but the plugins directory (needed for
        # 'import processing') may not be on sys.path yet — e.g. on Linux apt
        # where python3-qgis is installed but the plugins path was never added.
        # Run platform setup anyway; all _setup_* functions are idempotent.
        logger.debug(
            f"'import qgis' already succeeds (qgis at {getattr(qgis, '__file__', '?')}); "
            f"running idempotent platform setup to ensure plugins path."
        )
        if system == "Windows":
            _setup_windows()
        elif system == "Darwin":
            _setup_macos()
        else:
            _setup_linux()
        return True
    except ImportError:
        logger.debug("'import qgis' failed pre-setup; configuring environment.")

    if system == "Windows":
        _setup_windows()
    elif system == "Darwin":
        _setup_macos()
    else:
        _setup_linux()

    try:
        import qgis  # noqa: F401
        logger.debug(f"QGIS Python bindings found and configured (qgis at {getattr(qgis, '__file__', '?')}).")
        return True
    except ImportError as exc:
        logger.debug(f"QGIS Python bindings not found after path setup: {exc}")
        return False


def _setup_windows() -> None:
    try:
        prefix = Path(find_qgis_prefix_path())
    except RuntimeError:
        logger.debug("QGIS not found on Windows; skipping env setup.")
        return

    conda_prefix = os.environ.get("CONDA_PREFIX")
    is_conda = bool(conda_prefix and str(prefix).startswith(conda_prefix))
    root = prefix if is_conda else prefix.parent.parent

    if is_conda:
        logger.debug(f"Strategy 3 (conda-forge): QGIS prefix {prefix}")
    else:
        logger.debug(f"Strategy 1/2 (standalone): QGIS root {root}, prefix {prefix}")

    if not is_conda:
        bundled = sorted((root / "apps").glob("Python3*"), reverse=True)
        if bundled:
            expected = f"Python{sys.version_info.major}{sys.version_info.minor}"
            if bundled[0].name != expected:
                logger.warning(
                    f"Python version mismatch: QGIS bundles {bundled[0].name} "
                    f"but you are running {expected}. "
                    f"In-process QGIS (Strategy 1) will not be available; "
                    f"falling back to subprocess launcher (Strategy 2) if found."
                )
                return  # skip path setup; import qgis will fail → SubprocessProject fallback
            logger.debug(f"Bundled Python matches: {bundled[0].name}")
            bundled_site = bundled[0] / "Lib" / "site-packages"
            if bundled_site.exists() and str(bundled_site) not in sys.path:
                sys.path.append(str(bundled_site))
                logger.debug(f"Added bundled site-packages to sys.path: {bundled_site}")
        else:
            logger.debug(f"No bundled Python3* found under {root / 'apps'}.")

    for python_path in [prefix / "python", prefix / "python" / "plugins"]:
        if python_path.exists() and str(python_path) not in sys.path:
            sys.path.insert(0, str(python_path))
            logger.debug(f"Added to sys.path: {python_path}")
        elif not python_path.exists():
            logger.debug(f"Expected QGIS python path missing: {python_path}")

    # Register DLL directories and pre-load key libraries.
    # os.add_dll_directory() only covers .pyd loading by Python's import
    # machinery; transitive dependencies loaded by those .pyd files via
    # Windows LoadLibrary are not covered. Pre-loading with ctypes puts DLLs
    # into the process module table so later LoadLibrary calls find them there.
    dll_dirs = [root / "bin", root / "apps" / "Qt5" / "bin", prefix / "bin"]
    for dll_dir in dll_dirs:
        if dll_dir.exists():
            os.environ["PATH"] = str(dll_dir) + os.pathsep + os.environ.get("PATH", "")
            if hasattr(os, "add_dll_directory"):
                _dll_directory_handles.append(os.add_dll_directory(str(dll_dir)))
                logger.debug(f"Registered DLL directory: {dll_dir}")
        else:
            logger.debug(f"DLL directory not present, skipping: {dll_dir}")

    if not is_conda:
        import ctypes
        gdal_dlls = sorted((root / "bin").glob("gdal*.dll"))
        logger.debug(f"Pre-loading native libraries ({len(gdal_dlls)} gdal*.dll found).")
        for dll in [root / "apps" / "Qt5" / "bin" / "Qt5Core.dll", *gdal_dlls,
                    prefix / "bin" / "qgis_core.dll", prefix / "python" / "qgis" / "_core.pyd"]:
            if dll.exists():
                try:
                    ctypes.CDLL(str(dll))
                    logger.debug(f"Pre-loaded: {dll.name}")
                except OSError as exc:
                    logger.debug(f"Pre-load failed for {dll.name}: {exc}")
            else:
                logger.debug(f"Native library not present, skipping: {dll}")

    prefix_fwd = str(prefix).replace("\\", "/")
    strategy = "3 (conda-forge)" if is_conda else "1 (standalone, in-process)"
    logger.debug(f"Windows env configured — Strategy {strategy}, QGIS_PREFIX_PATH={prefix_fwd}")
    os.environ.setdefault("QGIS_PREFIX_PATH", prefix_fwd)
    os.environ.setdefault("GDAL_FILENAME_IS_UTF8", "YES")
    os.environ.setdefault("VSI_CACHE", "TRUE")
    os.environ.setdefault("VSI_CACHE_SIZE", "1000000")
    if not is_conda:
        os.environ.setdefault(
            "QT_PLUGIN_PATH",
            os.pathsep.join([str(prefix / "qtplugins"), str(root / "apps" / "qt5" / "plugins")]),
        )


def _setup_macos() -> None:
    try:
        prefix = Path(find_qgis_prefix_path())
    except RuntimeError:
        logger.debug("QGIS not found on macOS; skipping env setup.")
        return

    logger.debug(f"Configuring macOS env for QGIS prefix: {prefix}")
    resources = prefix.parent / "Resources"
    for p in [str(resources / "python"), str(resources / "python" / "plugins")]:
        if p not in sys.path:
            sys.path.insert(0, p)
            logger.debug(f"Added to sys.path: {p}")

    lib_path = prefix / "lib"
    if lib_path.exists():
        existing = os.environ.get("DYLD_LIBRARY_PATH", "")
        os.environ["DYLD_LIBRARY_PATH"] = str(lib_path) + (os.pathsep + existing if existing else "")
        logger.debug(f"Added to DYLD_LIBRARY_PATH: {lib_path}")
    else:
        logger.debug(f"lib path not present, skipping DYLD_LIBRARY_PATH: {lib_path}")

    os.environ.setdefault("QGIS_PREFIX_PATH", str(prefix))
    logger.debug(f"macOS env configured — QGIS_PREFIX_PATH={os.environ['QGIS_PREFIX_PATH']}")


def _setup_linux() -> None:
    try:
        prefix = Path(find_qgis_prefix_path())
    except RuntimeError:
        logger.debug("QGIS not found on Linux; skipping env setup.")
        return

    logger.debug(f"Configuring Linux env for QGIS prefix: {prefix}")
    for p in [str(prefix / "share" / "qgis" / "python"),
              str(prefix / "share" / "qgis" / "python" / "plugins")]:
        if p not in sys.path:
            sys.path.insert(0, p)
            logger.debug(f"Added to sys.path: {p}")

    lib_path = prefix / "lib"
    if lib_path.exists():
        existing = os.environ.get("LD_LIBRARY_PATH", "")
        os.environ["LD_LIBRARY_PATH"] = str(lib_path) + (os.pathsep + existing if existing else "")
        logger.debug(f"Added to LD_LIBRARY_PATH: {lib_path}")
    else:
        logger.debug(f"lib path not present, skipping LD_LIBRARY_PATH: {lib_path}")

    os.environ.setdefault("QGIS_PREFIX_PATH", str(prefix))
    logger.debug(f"Linux env configured — QGIS_PREFIX_PATH={os.environ['QGIS_PREFIX_PATH']}")
