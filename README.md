# qgis-project
Quickly create QGIS projects using Python


## Installation

1) Install the package via `pip install qgis-project`
1) This package requires a functioning conda installation to work. See [the docs](https://www.anaconda.com/docs/getting-started/miniconda/main) for installation instructions.
1) Create the required auxiliary conda environment with necessary packages via
    ```
    wget https://github.com/ColinMoldenhauer/qgis-project/blob/main/environment.yml
    conda env create -f environment.yaml
    ```

**Further info**: this package makes use of the `qgis=3.28.12` package, as distributed via conda. This old version has some outdated dependencies and in order not to interfere with your working environment, the dependencies that this package requires under the hood are installed in a separate auxiliary environment (by default called `qgis-env`). There might be a better way to handle these auxiliary dependencies, if you know one, please let me know.