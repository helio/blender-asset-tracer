"""Create a BAT-pack for the given blend file."""


def add_parser(subparsers):
    """Add argparser for this subcommand."""

    parser = subparsers.add_parser('pack', help=__doc__)
    parser.set_defaults(func=cli_pack)


def cli_pack(args):
    raise NotImplementedError('bat pack not implemented yet')
