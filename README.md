# Blender Asset Tracer BAT🦇

Script to manage assets with Blender.

Blender Asset Tracer, a.k.a. BAT🦇, is the replacement of
[BAM](https://developer.blender.org/diffusion/BAM/) and
[blender-file](https://developer.blender.org/source/blender-file/)

Development is driven by choices explained in [T54125](https://developer.blender.org/T54125).

## Setting up development environment

```
python3.9 -m venv .venv
. ./.venv/bin/activate
pip install -U pip
pip install poetry black
poetry install
mypy --install-types
```


## Uploading to S3-compatible storage

BAT Pack supports uploading to S3-compatible storage. This requires a credentials file in
`~/.aws/credentials`. Replace the all-capital words to suit your situation.

    [ENDPOINT]
    aws_access_key_id = YOUR_ACCESS_KEY_ID
    aws_secret_access_key = YOUR_SECRET

You can then send a BAT Pack to the storage using a target `s3:/ENDPOINT/bucketname/path-in-bucket`,
for example:

    bat pack my_blendfile.blend s3:/storage.service.cloud/jobs/awesome_work

This will upload the blend file and its dependencies to `awesome_work/my_blendfile.blend` in
the `jobs` bucket.


## Paths

There are two object types used to represent file paths. Those are strictly separated.

1. `bpathlib.BlendPath` represents a path as stored in a blend file. It consists of bytes, and is
   blendfile-relative when it starts with `//`. It can represent any path from any OS Blender
   supports, and as such should be used carefully.
2. `pathlib.Path` represents an actual path, possibly on the local filesystem of the computer
   running BAT. Any filesystem operation (such as checking whether it exists) must be done using a
   `pathlib.Path`.

When it is necessary to interpret a `bpathlib.BlendPath` as a real path instead of a sequence of
bytes, BAT first attempts to decode it as UTF-8. If that fails, the local filesystem encoding is
used. The latter is also no guarantee of correctness, though.


## Type checking

The code statically type-checked with [mypy](http://mypy-lang.org/).

Mypy likes to see the return type of `__init__` methods explicitly declared as `None`. Until issue
[#604](https://github.com/python/mypy/issues/604) is resolved, we just do this in our code too.


## Code Example

BAT can be used as a Python library to inspect the contents of blend files, without having to
open Blender itself. Here is an example showing how to determine the render engine used:

    #!/usr/bin/env python3.7
    import json
    import sys
    from pathlib import Path

    from blender_asset_tracer import blendfile
    from blender_asset_tracer.blendfile import iterators

    if len(sys.argv) != 2:
        print(f'Usage: {sys.argv[0]} somefile.blend', file=sys.stderr)
        sys.exit(1)

    bf_path = Path(sys.argv[1])
    bf = blendfile.open_cached(bf_path)

    # Get the first window manager (there is probably exactly one).
    window_managers = bf.find_blocks_from_code(b'WM')
    assert window_managers, 'The Blend file has no window manager'
    window_manager = window_managers[0]

    # Get the scene from the first window.
    windows = window_manager.get_pointer((b'windows', b'first'))
    for window in iterators.listbase(windows):
        scene = window.get_pointer(b'scene')
        break

    # BAT can only return simple values, so it can't return the embedded
    # struct 'r'. 'r.engine' is a simple string, though.
    engine = scene[b'r', b'engine'].decode('utf8')
    xsch = scene[b'r', b'xsch']
    ysch = scene[b'r', b'ysch']
    size = scene[b'r', b'size'] / 100.0

    render_info = {
        'engine': engine,
        'frame_pixels': {
            'x': int(xsch * size),
            'y': int(ysch * size),
        },
    }

    json.dump(render_info, sys.stdout, indent=4, sort_keys=True)
    print()

To understand the naming of the properties, look at Blender's `DNA_xxxx.h` files with struct
definitions. It is those names that are accessed via `blender_asset_tracer.blendfile`. The
mapping to the names accessible in Blender's Python interface can be found in the `rna_yyyy.c`
files.


## Code Guidelines

This section documents some guidelines for the code in BAT.

### Avoiding Late Imports

All imports should be done at the top level of the file, and not inside
functions. The goal is to ensure that, once imported, a (sub)module of BAT can
be used without having to import more parts of BAT.

This requirement helps to keep Blender add-ons separated, as an add-on can
import the modules of BAT it needs, then remove them from `sys.modules` and
`sys.path` so that other add-ons don't see them. This should reduce problems
with various add-ons shipping different versions of BAT.

## Publishing a New Release

For uploading packages to PyPi, an API key is required; username+password will
not work.

First, generate an API token at https://pypi.org/manage/account/token/. Then,
use this token when publishing instead of your username and password.

As username, use `__token__`.
As password, use the token itself, including the `pypi-` prefix.

See https://pypi.org/help/#apitoken for help using API tokens to publish. This
is what I have in `~/.pypirc`:

```
[distutils]
index-servers =
    bat

# Use `twine upload -r bat` to upload with this token.
[bat]
  repository = https://upload.pypi.org/legacy/
  username = __token__
  password = pypi-abc-123-blablabla
```

```
. ./.venv/bin/activate
pip install twine

poetry build
twine check dist/blender_asset_tracer-1.15.tar.gz dist/blender_asset_tracer-1.15-*.whl
twine upload -r bat dist/blender_asset_tracer-1.15.tar.gz dist/blender_asset_tracer-1.15-*.whl
```
