import logging
import pathlib
import typing

log = logging.getLogger(__name__)


class DoesNotExist(OSError):
    """Indicates a path does not exist on the filesystem."""

    def __init__(self, path: pathlib.Path):
        super().__init__(path)
        self.path = path


def expand_sequence(path: pathlib.Path) -> typing.Iterator[pathlib.Path]:
    """Expand a file sequence path into the actual file paths.

    :param path: can be either a glob pattern (must contain a * character)
        or the path of the first file in the sequence.
    """

    if '*' in str(path):  # assume it is a glob
        import glob
        log.debug('expanding glob %s', path)
        for fname in sorted(glob.glob(str(path), recursive=True)):
            yield pathlib.Path(fname)
        return

    if not path.exists():
        raise DoesNotExist(path)

    if path.is_dir():
        raise TypeError('path is a directory: %s' % path)

    log.debug('expanding file sequence %s', path)

    import string
    stem_no_digits = path.stem.rstrip(string.digits)
    if stem_no_digits == path.stem:
        # Just a single file, no digits here.
        yield path
        return

    # Return everything start starts with 'stem_no_digits' and ends with the
    # same suffix as the first file. This may result in more files than used
    # by Blender, but at least it shouldn't miss any.
    pattern = '%s*%s' % (stem_no_digits, path.suffix)
    yield from sorted(path.parent.glob(pattern))
