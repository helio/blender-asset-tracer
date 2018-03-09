# Blender Asset Tracer BAT🦇

Script to manage assets with Blender.

Blender Asset Tracer, a.k.a. BAT🦇, is the replacement of
[BAM](https://developer.blender.org/diffusion/BAM/) and
[blender-file](https://developer.blender.org/source/blender-file/)

Development is driven by choices explained in [T54125](https://developer.blender.org/T54125).


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
