# Notes
A collection of ideas, development notes, etc.

## Notes
- [Cheat Sheet](https://docs.qgis.org/3.40/en/docs/pyqgis_developer_cookbook/cheat_sheet.html)
- [.bat script](https://gis.stackexchange.com/questions/347255/using-qgis-python-interpreter-outside-qgis)
- ["running custom applications"](https://docs.qgis.org/3.40/en/docs/pyqgis_developer_cookbook/intro.html#running-custom-applications)
    - `export PYTHONPATH=/c/Program\ Files/QGIS\ 3.28.0/apps/qgis/python/`
    - `export PYTHONPATH=/c/Program\ Files/QGIS\ 3.28.0/apps/qgis/python/`
- ["QGIS standalone repo"](https://github.com/MarByteBeep/pyqgis-standalone): unclear so far what it's doing



## Environment Strategies
Accessing QGIS Python bindings proofed to be much more challenging than expected.
This chapter summarizes different paradigms and attempts of building on top of the QGIS Python API.

### Criteria
- **QGIS version compatibility**: all features of the user's QGIS version should be supported
- **platform independence**: as this is a Python package, it should run on any platform
- **environment independence**: should be installable into any python environment (pip, conda)
- **ease/robustness of installation**: installation should be quick, easy and robust
- **complexity/hackyness**: the environment handling should be as simple as possible, avoiding hacky solutions where possible

### Strategy 1) Access the local QGIS installation
Every QGIS install comes with an inbuilt Python interpreter, designed for Python scripts within QGIS.
This works fine, however we want a solution that makes the QGIS Python API accessable from outside the program, such that we don't have to run the scripts from within QGIS every time.

**Checklist**
- ✅ version: automatically compatible with user's QGIS install
- ✅ platform: bundled python for correct platform
- ✅ environment: QGIS Python should be independent of any environment
- ✅ installation: no additional dependencies needed to access QGIS Python API
- ✅ complexity: no additional dependencies needed to access QGIS Python API
- ⚪ complexity: no additional dependencies needed to access QGIS Python API

#### Attempts & Problems
- ❌ accessing built-in QGIS python is a pain in the ass
...

#### Verdict
Not suitable.


### Strategy 2) Isolated conda-environment


### Strategy 3) Install `qgis` via conda

### Attempts Windows
```
conda env create -f environment_platform_independent.yml
conda activate qgis-env-pi  # not yet enough, needs more steps

# TODO: $CONDA_PREFIX returns Windows-style path with \, need to convert?
export PYTHONPATH=$CONDA_PREFIX/Library/python/qgis:$CONDA_PREFIX/Library/python:$PYTHONPATH
export PATH=$CONDA_PREFIX/Library/bin:$CONDA_PREFIX/Library/python/qgis:$PATH








### Strategy ...) Run QGIS with script
According to [stackoverflow](https://gis.stackexchange.com/questions/29580/running-simple-python-script-for-qgis-from-outside), QGIS can be called from the CL, passing a script to execute.

**Open question**: can this create a project as well?