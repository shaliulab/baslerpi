import pathlib
from setuptools import setup, find_packages


# The directory containing this file
HERE = pathlib.Path(__file__).parent

# The text of the README file
README = (HERE / "README.md").read_text()

# name of package and name of folder containing it
PACKAGE_NAME = "baslerpi"

# attention. you need to update the numbers ALSO in the imgstore/__init__.py file
version = "1.1.1"

with open(f"{PACKAGE_NAME}/_version.py", "w") as fh:
    fh.write(f"__version__ = '{version}'\n")


# This call to setup() does all the work
setup(
    name=PACKAGE_NAME,
    version=version,
    # description="High resolution monitoring of Drosophila",
    # long_description=README,
    # long_description_content_type="text/markdown",
    ##url="https://github.com/realpython/reader",
    # author="Antonio Ortega",
    # author_email="antonio.ortega@kuleuven.be",
    # license="MIT",
    # classifiers=[
    #    "License :: OSI Approved :: MIT License",
    #    "Programming Language :: Python :: 3",
    #    "Programming Language :: Python :: 3.7",
    # ],
    scripts=["src/rsync_transfer.sh"],
    packages=find_packages(),
    # include_package_data=True,
    install_requires=[
        "gitpython",
        "opencv-python",
        "pyaml",
        "scikit-video",
        "imgstore",
        "pypylon",
        "tqdm",
    ],
    entry_points={
        "console_scripts": [
            "baslerpi=baslerpi.bin.run:main",
            "baslerpi-test=baslerpi.io.cameras.basler:main",
        ]
    },
)
