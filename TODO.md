
EXECUTOR STRATEGY
- reduce code duplication

- features
    - "overwrite" logic
        - `add_layer(..., overwrite=True)` ?
    - ~~double-check calculation of raster min/max~~
    - quickmap plugin support?
    - ~~on start, zoom to extent (either first/last layer or all)~~
    - ~~add layers (raster, vector)~~
    - "special formats" supported? netcdf, zarr, etc.
    - interact with layer plugins (OSM, etc.)
        - plugins are python?
        - install directly in same environment as `qgis-project`?
        - example plugins
            - [recommended](https://docs.qgis.org/3.44/en/docs/training_manual/qgis_plugins/plugin_examples.html)
            -
    - ~~jupyter widget support?~~
        - maybe via https://github.com/vispy/jupyter_rfb
        - more info
            - https://discourse.jupyter.org/t/qt-and-jupyterlab/10229/3
            - https://github.com/jupyterhub/jupyter-remote-desktop-proxy
            - https://en.wikipedia.org/wiki/VNC
        - preview via
        ```python
        from IPython.display import Image
        import io
        from PyQt5.QtCore import QSize
        from qgis.gui import QgsMapCanvas

        buf = QBuffer()
        canvas.grab().toImage().save(buf, "PNG")
        display(Image(buf.data()))
        ```
    - classic GIS functions
        - info https://docs.qgis.org/3.44/en/docs/user_manual/processing/console.html
            - different import mentioned here?
        - ~~set CRS~~
        - reproject
        - etc.
        - ~~raster processing~~
        - ~~vector processing~~
    - convenience
        - ~~print layer stack~~

DOCS
- ~~explicit reference what this package IS and what it ISN'T~~
    - IS: thin wrapper around QGIS' most essential functions
        - loading layers (vector/raster, local/web)
        - basic visualization
        - basic processing
    - ISN'T: advanced analysis
        - complex visual analysis
        - mapping


- QGIS detection
    - requirements
        - dynamic determination of right dependencies (i.e. numpy<2)
            -> dynamic install upon `pip install qgis-project` possible?
        - alternatively, run the .bat/.sh(?) in a subprocess?
    - how exactly does it work?
    - what about multiple versions?
        - in particular conda installed vs local
        - how to switch/choose (env, input, etc)
    - strategy 3 (conda)
        - why do we need to add any paths manually to PYTHONPATH? manual fix of conda error?

TESTS
- ~~tests as github workflows~~
- ~~tests for combinations of operating system, strategy, QGIS version~~
- add standalone QGIS tests for linux, macos

- python version handling
    - how to know which python is supported by installed QGIS?
    - really need to `raise RuntimeError` if version mismatch?

- docs
    - highlight which part of the .bat is replicated where in the setup function

miscellaneous
- ~~`proj.open()` empty open saves to tmp file and opens?~~
- ~~`proj.save("proj.qgz")` save manually without open~~
