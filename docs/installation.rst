Installation
============

BAT🦇 can be installed with `pip`::

    pip install blender-asset-tracer


Requirements and Dependencies
-----------------------------

In order to run BAT you need Python 3.5; BAT always targets the Python version
used in the `latest Blender release`_.

.. _`latest Blender release`: https://www.blender.org/download

Apart from Python, BAT has very little external dependencies. When only working
with the local filesystem (which includes network shares; anything that your
computer can simply copy files to) it has no extra dependencies. Uploading to
S3-compatible storage requires the `boto3` library.


Development dependencies
------------------------

In order to start developing on BAT you need a bit more. First use Git_ to get a
copy of the source::

    git clone https://gitlab.com/dr.sybren/blender-asset-tracer.git
    virtualenv -p /path/to/python3 bat-venv
    . ./bat-venv/bin/activate
    cd blender-asset-tracer
    pip3 install -U -r requirements-dev.txt

.. _Git: https://git-scm.com/
