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
    common.add_flag(parser, 'nonrecursive',
                    help='Limit to direct dependencies of the named blend file')
    common.add_flag(parser, 'json', help='Output as JSON instead of human-readable text')


def cli_list(args):
    from blender_asset_tracer import tracer

    bpath = args.blendfile
    if not bpath.exists():
        log.fatal('File %s does not exist', args.blendfile)
        return 3

    cwd = pathlib.Path.cwd()

    reported_assets = set()
    last_reported_bfile = None

    recursive = not args.nonrecursive
    for usage in tracer.deps(bpath, recursive=recursive):
        filepath = usage.block.bfile.filepath.absolute()
        if filepath != last_reported_bfile:
            print(filepath.relative_to(cwd))
        last_reported_bfile = filepath

        for assetpath in usage.files():
            assetpath = assetpath.resolve()
            if assetpath in reported_assets:
                log.debug('Already reported %s', assetpath)
                continue

            try:
                print('   ', assetpath.relative_to(cwd))
            except ValueError:
                print('   ', assetpath)
            reported_assets.add(assetpath)
