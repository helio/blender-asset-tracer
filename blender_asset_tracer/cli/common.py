"""Common functionality for CLI parsers."""


def add_flag(argparser, flag_name: str, **kwargs):
    """Add a CLI argument for the flag.

    The flag defaults to False, and when present on the CLI stores True.
    """

    argparser.add_argument('-%s' % flag_name[0],
                           '--%s' % flag_name,
                           default=False,
                           action='store_true',
                           **kwargs)


