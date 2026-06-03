# Notes
A collection of ideas, development notes, etc.

## Implementation strategies

### Strategy 1) Manual setup (aka dependency hell)
- mimick bundled python's env setup in user's python environment
    - ...
- issue: version conflict of bundled and user installed packages
    - example
    ```
    conda create -n py39 python=3.9 ...
    conda install numpy     # will install modern numpy>2
    python scripts/manual_test.py   # crashes due to bundled packages requiring numpy<2 (but user numpy taking precedence)
    ```
- variant: mirror bundled repo?

### Strategy 2) Execution wrapper
- no dependency issues
    - QGIS bundled python lives seperately from user env (conda, venv, etc.)
    - would execute C:\Program Files\QGIS 3.28.0\bin\python-qgis.bat` (this windows)
        - calls C:\Program Files\QGIS 3.28.0\bin\o4w_env.bat and other setup scripts
- issue: need to install `qgis-project` into bundled python's site-packages
    - how?
- issue: no handling of internal QGIS objects
    - no live objects returned
    - no interactive use


### Strategy 3) QGIS via conda only
- dependencies handled by conda solver
- issue: doesnt tap into local QGIS installation
- issue: multiple QGIS installations