# Blender Asset Tracer BAT🦇

Script to manage assets with Blender.

Blender Asset Tracer, a.k.a. BAT🦇, is the replacement of
[BAM](https://developer.blender.org/diffusion/BAM/) and
[blender-file](https://developer.blender.org/source/blender-file/)

Development is driven by choices explained in [T54125](https://developer.blender.org/T54125).


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
