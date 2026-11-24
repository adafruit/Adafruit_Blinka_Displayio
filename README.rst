Introduction
============

.. image:: https://readthedocs.org/projects/adafruit-blinka-displayio/badge/?version=latest
    :target: https://adafruit-blinka-displayio.readthedocs.io/en/latest/
    :alt: Documentation Status

.. image:: https://img.shields.io/discord/327254708534116352.svg
    :target: https://adafru.it/discord
    :alt: Discord

.. image:: https://github.com/adafruit/Adafruit_Blinka_Displayio/workflows/Build%20CI/badge.svg
    :target: https://github.com/adafruit/Adafruit_Blinka_Displayio/actions
    :alt: Build Status

.. image:: https://img.shields.io/badge/code%20style-black-000000.svg
    :target: https://github.com/psf/black
    :alt: Code Style: Black

displayio for Blinka


Dependencies
=============
This driver depends on:

* `Adafruit Blinka <https://github.com/adafruit/Adafruit_Blinka>`_

Installing from PyPI
=====================

On supported GNU/Linux systems like the Raspberry Pi, you can install the driver locally `from
PyPI <https://pypi.org/project/adafruit-blinka-displayio/>`_. To install for current user:

.. code-block:: shell

    pip3 install adafruit-blinka-displayio

To install system-wide (this may be required in some cases):

.. code-block:: shell

    sudo pip3 install adafruit-blinka-displayio

To install in a virtual environment in your current project:

.. code-block:: shell

    mkdir project-name && cd project-name
    python3 -m venv .env
    source .env/bin/activate
    pip3 install adafruit-blinka-displayio

Using multiple displays
=======================

Blinka Displayio allows one display by default. With Blinka 10.4.0 or newer,
set a positive integer at the top level of ``settings.toml`` in your program's
working directory to raise the limit.

.. code-block:: toml

    BLINKA_DISPLAY_LIMIT = 2

Blinka Displayio reads the limit at import and applies it separately to
displays and registered display buses. The environment variable
``BLINKA_DISPLAY_LIMIT`` takes precedence over the file. With older versions of
Blinka, set the environment variable before launching your program.

.. code-block:: shell

    BLINKA_DISPLAY_LIMIT=2 python3 my_display_program.py

The default splash can belong to one display at a time. Assign each display
its own root group.

Use separate bitmap and palette objects for content that changes on each
display. A refresh can consume the pending updates on a shared bitmap or
palette before the other display redraws.

When ``BusDisplay`` instances share a hardware bus, initialize each one with
``auto_refresh=False``. After setup, either enable automatic refresh and let
the background worker refresh the displays, or leave automatic refresh off
for every display on the bus and call ``refresh()`` on them one at a time.

Contributing
============

Contributions are welcome! Please read our `Code of Conduct
<https://github.com/adafruit/Adafruit_blinka_CircuitPython_displayio/blob/master/CODE_OF_CONDUCT.md>`_
before contributing to help this project stay welcoming.

To make sure your pull request will pass the commit checks, use pre-commit to check your code formatting. Please see the guide page here for more details: https://learn.adafruit.com/contribute-to-circuitpython-with-git-and-github/check-your-code

Documentation
=============

For information on building library documentation, please check out `this guide <https://learn.adafruit.com/creating-and-sharing-a-circuitpython-library/sharing-our-docs-on-readthedocs#sphinx-5-1>`_.
