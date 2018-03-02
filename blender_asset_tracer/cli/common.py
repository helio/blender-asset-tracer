"""Common functionality for CLI parsers."""
import pathlib


def add_flag(argparser, flag_name: str, **kwargs):
    """Add a CLI argument for the flag.

    The flag defaults to False, and when present on the CLI stores True.
    """

    argparser.add_argument('-%s' % flag_name[0],
                           '--%s' % flag_name,
                           default=False,
                           action='store_true',
                           **kwargs)


def shorten(cwd: pathlib.Path, somepath: pathlib.Path) -> pathlib.Path:
    """Return 'somepath' relative to CWD if possible."""
    try:
        return somepath.relative_to(cwd)
    except ValueError:
        return somepath
