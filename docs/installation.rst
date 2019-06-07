Installation
============

BAT🦇 can be installed with `pip`::

    pip3 install blender-asset-tracer


Requirements and Dependencies
-----------------------------

In order to run BAT you need Python 3.5 or newer; BAT always targets the Python version
used in the `latest Blender release`_.

.. _`latest Blender release`: https://www.blender.org/download

Apart from Python, BAT has very little external dependencies. When only working
with the local filesystem (which includes network shares; anything that your
computer can simply copy files to) it has no extra dependencies. Uploading to
S3-compatible storage requires the `boto3` library.


Development dependencies
------------------------

In order to start developing on BAT you need a bit more. Dependencies are managed by Poetry_::

    git clone https://gitlab.com/dr.sybren/blender-asset-tracer.git
    cd blender-asset-tracer
    pip3 install poetry
    poetry install

.. _Poetry: https://poetry.eustace.io/
