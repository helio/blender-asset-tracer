"""Blender path support.

Does not use pathlib, because we may have to handle POSIX paths on Windows
or vice versa.
"""

import os.path
import string


class BlendPath(bytes):
    """A path within Blender is always stored as bytes."""

    def __new__(cls, path):
        if isinstance(path, str):
            # As a convenience, when a string is given, interpret as UTF-8.
            return bytes.__new__(cls, path.encode('utf-8'))
        return bytes.__new__(cls, path)

    def __str__(self) -> str:
        """Decodes the path as UTF-8, replacing undecodable bytes.

        Undecodable bytes are ignored so this function can be safely used
        for reporting.
        """
        return self.decode('utf8', errors='replace')

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

    def absolute(self, root: bytes=None) -> 'BlendPath':
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
