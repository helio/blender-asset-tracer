"""List dependencies of a blend file."""
import logging
import pathlib

from . import common

log = logging.getLogger(__name__)


def add_parser(subparsers):
    """Add argparser for this subcommand."""

    parser = subparsers.add_parser('list', help=__doc__)
    parser.set_defaults(func=cli_list)
    parser.add_argument('blendfile', type=pathlib.Path)
    common.add_flag(parser, 'recursive', help='Also report dependencies of dependencies')
    common.add_flag(parser, 'json', help='Output as JSON instead of human-readable text')


def cli_list(args):
    from blender_asset_tracer import tracer

    bpath = args.blendfile
    if not bpath.exists():
        log.fatal('File %s does not exist', args.blendfile)
        return 3

    reported_files = set()
    for usage in tracer.deps(bpath, recursive=args.recursive):
        for path in usage.files():
            path = path.resolve()
            if path in reported_files:
                log.debug('Already reported %s', path)
                continue
            print(path)
            reported_files.add(path)
