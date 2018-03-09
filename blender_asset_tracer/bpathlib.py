"""Blender path support.

Does not use pathlib, because we may have to handle POSIX paths on Windows
or vice versa.
"""

import os.path
import pathlib
import string
import sys


class BlendPath(bytes):
    """A path within Blender is always stored as bytes."""

    def __new__(cls, path):
        if isinstance(path, pathlib.Path):
            path = str(path).encode('utf-8')
        if not isinstance(path, bytes):
            raise TypeError('path must be bytes or pathlib.Path, but is %r' % path)

        return super().__new__(cls, path)

    @classmethod
    def mkrelative(cls, asset_path: pathlib.Path, bfile_path: pathlib.Path) -> 'BlendPath':
        """Construct a BlendPath to the asset relative to the blend file."""
        from collections import deque

        bdir_parts = deque(bfile_path.absolute().parent.parts)
        asset_parts = deque(asset_path.absolute().parts)

        # Remove matching initial parts. What is left in bdir_parts represents
        # the number of '..' we need. What is left in asset_parts represents
        # what we need after the '../../../'.
        while bdir_parts:
            if bdir_parts[0] != asset_parts[0]:
                break
            bdir_parts.popleft()
            asset_parts.popleft()

        rel_asset = pathlib.Path(*asset_parts)
        # TODO(Sybren): should we use sys.getfilesystemencoding() instead?
        rel_bytes = str(rel_asset).encode('utf-8')
        as_bytes = b'//' + len(bdir_parts) * b'../' + rel_bytes
        return cls(as_bytes)

    def __str__(self) -> str:
        """Decodes the path as UTF-8, replacing undecodable bytes.

        Undecodable bytes are ignored so this function can be safely used
        for reporting.
        """
        return self.decode('utf8', errors='replace')

    def __truediv__(self, subpath: bytes):
        """Slash notation like pathlib.Path."""
        sub = BlendPath(subpath)
        if sub.is_absolute():
            raise ValueError("'a / b' only works when 'b' is a relative path")
        return BlendPath(os.path.join(self, sub))

    def __rtruediv__(self, parentpath: bytes):
        """Slash notation like pathlib.Path."""
        if self.is_absolute():
            raise ValueError("'a / b' only works when 'b' is a relative path")
        return BlendPath(os.path.join(parentpath, self))

    def to_path(self) -> pathlib.Path:
        """Convert this path to a pathlib.Path.

        Interprets the path as UTF-8, and if that fails falls back to the local
        filesystem encoding.

        Note that this does not handle blend-file-relative paths specially, so
        the returned Path may still start with '//'.
        """
        # TODO(Sybren): once we target Python 3.6, implement __fspath__().
        try:
            decoded = self.decode('utf8')
        except UnicodeDecodeError:
            decoded = self.decode(sys.getfilesystemencoding())
        return pathlib.Path(decoded)

    def is_blendfile_relative(self) -> bool:
        return self[:2] == b'//'

    def is_absolute(self) -> bool:
        if self.is_blendfile_relative():
            return False
        if self[0:1] == b'/':
            return True

        # Windows style path starting with drive letter.
        if (len(self) >= 3 and
                (self.decode('utf8'))[0] in string.ascii_letters and
                self[1:2] == b':' and
                self[2:3] in {b'\\', b'/'}):
            return True

        return False

    def absolute(self, root: bytes = None) -> 'BlendPath':
        """Determine absolute path.

        :param root: root directory to compute paths relative to.
            For blendfile-relative paths, root should be the directory
            containing the blendfile. If not given, blendfile-relative
            paths cause a ValueError but filesystem-relative paths are
            resolved based on the current working directory.
        """
        if self.is_absolute():
            return self

        if self.is_blendfile_relative():
            my_relpath = self[2:]  # strip off leading //
        else:
            my_relpath = self
        return BlendPath(os.path.join(root, my_relpath))
