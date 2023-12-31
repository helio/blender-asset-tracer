# Blender Asset Tracer changelog

This file logs the changes that are actually interesting to users (new features,
changed functionality, fixed bugs).

# Version 1.16 (in development)

- Add `BlendFileBlock.raw_data()` and `.as_string()` functions. These functions interpret the data in a `BlendFileBlock` as either `bytes` or `string`. This can be used to obtain the contents of a `char*` (instead of the more common embedded `char[N]` array).

# Version 1.15 (2022-12-16)

- Add support for fluid simulation caches.

# Version 1.14 (2022-09-12)

- While tracing dependencies, call the progress callback function before opening a blend file, instead of before iterating over its contents. The opening (and loading of SDNA) takes a significant amount of time, so this will make any UI (like the Flamenco add-on) report the right filename when waiting for big files.

# Version 1.13 (2022-07-14)

- Improve an error message when packing fails. It now not only mentions that something went wrong, but also which file and which operation on that file (copy or move) was involved.

# Version 1.12 (2022-03-25)

- Removed "late imports", to help isolate Blender add-ons bundling BAT from each other.
- Support writing `int` and `float` types.
- Decided to *not* support the Shaman API of Flamenco 3.x in BAT. The support for that protocol will be implemented in the Flamenco 3.x add-on for Blender, and not in BAT itself. A new future version of BAT will remove support for the Shaman API altogether.
- Bumped the required version of Python to 3.7. This was already done back in version 1.5, but now also the MyPy configuration takes it into account.
- Support Python 3.10 (for Blender 3.1)

# Version 1.11 (2022-02-18)

- Support UDIM images.

# Version 1.10 (2022-02-03)

- Avoid doubly-compressing ZStandard (Blender 3) compressed files.

# Version 1.9 (2021-11-19)

- Add `bat version` command to print just the version number and exit.

# Version 1.8 (2021-11-09)

- Compatibility with read-only source files. When packing, file permissions are no longer copied. This means that BAT can modify paths in packed files, even when the source files were read-only.

# Version 1.7 (2021-11-05)

- Add optional support for ZStandard compression, which is used to compress blend files by Blender 3.0+.
  The `zstandard` module is binary, and without it installed BAT will still be able to work in a pure-Python environment. It just won't be able to open compressed files from Blender 3.0 or newer.


## Version 1.6 (2021-07-27)

- Support linked collections used as input in a Geometry Nodes modifier.
- Support collections, objects, images, and textures used as default values in nodes.


## Version 1.5.1 (2021-07-22)

- Add log warning if SegmentationFault caused by dereferencing invalid pointer is silenced when strict_pointer_mode is turned off.

## Version 1.5 (2021-07-22)

- Drop support for Python 3.5 and 3.6, and add support for 3.8 and 3.9.


## Version 1.4.1 (2021-07-22)

- Reverted unintended bump of required Python version.


## Version 1.4 (2021-07-22)

- Add a *Strict Pointer Mode* setting, which determines what happens when a pointer to an unknown datablock is dereferenced. When enabled, a `SegmentationFault` exception stops the program execution. This has always been the behaviour of BAT, but it now has a name and can be disabled.

  On the commandline Strict Pointer Mode is now disabled by default; it can be enabled with the `-S` parameter (see `bat --help`).

  When BAT is used as library, Strict Pointer Mode is enabled by default, and can be disabled via `blender_asset_tracer.blendfile.set_strict_pointer_mode(False)`.


## Version 1.3.1 (2021-02-04)

- Remove assertion error when a library blend file linked from a Geometry Nodes modifier does not exist.


## Version 1.3 (2021-02-02)

- When creating a BAT pack, symlinks are no longer followed. This allows BAT-packing a directory structure with symlinked files (such as a Shaman checkout).
- When creating a BAT pack, mapped network drives are no longer changed from a drive letter to UNC notation. For example, when mapping a share `\\SERVER\Share` to drive letter `S:\`, BAT will now keep referencing `S:\` instead of rewriting paths to `\\SERVER\Share`.
- Better handling of drive letters, and of paths that cross drive boundaries.
- Better testing of Windows-specific cases when running the tests on Windows, and of POSIX-specific cases on other platforms.
- Add support for Geometry Nodes modifier.


## Version 1.2 (2019-10-09)

- Migrated from Pipenv to Poetry for managing Python package dependencies.
- Windows compatibility fix when using mapped network storage.
- Windows compatibility fix when using different assets with the same path but on different drives.
- Allow setting the Shaman JWT authentication token in the `SHAMAN_JWT_TOKEN` environment variable.
- Blender 2.81 compatibility fix (T69976).
- Fix for external smoke caches not being packed.
- Versions 1.2.1 and 1.2.2 are functionally identical to 1.2


## Version 1.1.1 (2019-04-18)

- Blender 2.79 / Python 3.5 compatibility fix.


## Version 1.1 (2019-03-25)

- Add support for Shaman (https://www.flamenco.io/docs/user_manual/shaman/)
- Add support for Alembic files referenced in linked-in libraries.


## Version 1.0 (2019-03-01)

- Base version after which changes will be recorded here.
