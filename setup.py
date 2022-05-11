# SPDX-FileCopyrightText: 2020 Melissa LeBlanc-Williams, written for Adafruit Industries
#
# SPDX-License-Identifier: MIT

"""A setuptools based setup module.

See:
https://packaging.python.org/en/latest/distributing.html
https://github.com/pypa/sampleproject
"""

from setuptools import setup, find_packages

# To use a consistent encoding
from codecs import open
from os import path
import sys

here = path.abspath(path.dirname(__file__))

requirements = [
    "Adafruit-Blinka>=7.0.0",
    "adafruit-circuitpython-typing",
    "pillow",
    "numpy",
]

if sys.version_info > (3, 9):
    requirements.append("pillow>=6.0.0")

# Get the long description from the README file
with open(path.join(here, "README.rst"), encoding="utf-8") as f:
    long_description = f.read()

setup(
    name="adafruit-blinka-displayio",
    use_scm_version=True,
    setup_requires=["setuptools_scm"],
    description="displayio for Blinka",
    long_description=long_description,
    long_description_content_type="text/x-rst",
    # The project's main homepage.
    url="https://github.com/adafruit/Adafruit_Blinka_Displayio",
    # Author details
    author="Adafruit Industries",
    author_email="circuitpython@adafruit.com",
    install_requires=requirements,
    # Choose your license
    license="MIT",
    # See https://pypi.python.org/pypi?%3Aaction=list_classifiers
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Libraries",
        "Topic :: System :: Hardware",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.7",
    ],
    # What does your project relate to?
    keywords="adafruit blinka circuitpython micropython displayio lcd tft display pitft",
    # You can just specify the packages manually here if your project is
    # simple. Or you can use find_packages().
    py_modules=["fontio", "terminalio", "paralleldisplay"],
    packages=["displayio"],
)
