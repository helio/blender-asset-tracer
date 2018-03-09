"""List dependencies of a blend file."""
import functools
import json
import logging
import pathlib
import sys

from blender_asset_tracer import trace
from . import common

log = logging.getLogger(__name__)


def add_parser(subparsers):
    """Add argparser for this subcommand."""

    parser = subparsers.add_parser('list', help=__doc__)
    parser.set_defaults(func=cli_list)
    parser.add_argument('blendfile', type=pathlib.Path)
    common.add_flag(parser, 'json', help='Output as JSON instead of human-readable text')


def cli_list(args):
    bpath = args.blendfile
    if not bpath.exists():
        log.fatal('File %s does not exist', args.blendfile)
        return 3

    if args.json:
        report_json(bpath)
    else:
        report_text(bpath)


def report_text(bpath):
    reported_assets = set()
    last_reported_bfile = None
    shorten = functools.partial(common.shorten, pathlib.Path.cwd())

    for usage in trace.deps(bpath):
        filepath = usage.block.bfile.filepath.absolute()
        if filepath != last_reported_bfile:
            print(shorten(filepath))
        last_reported_bfile = filepath

        for assetpath in usage.files():
            assetpath = assetpath.resolve()
            if assetpath in reported_assets:
                log.debug('Already reported %s', assetpath)
                continue

            print('   ', shorten(assetpath))
            reported_assets.add(assetpath)


class JSONSerialiser(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, pathlib.Path):
            return str(o)
        if isinstance(o, set):
            return sorted(o)
        return super().default(o)


def report_json(bpath):
    import collections

    # Mapping from blend file to its dependencies.
    report = collections.defaultdict(set)

    for usage in trace.deps(bpath):
        filepath = usage.block.bfile.filepath.absolute()
        for assetpath in usage.files():
            assetpath = assetpath.resolve()
            report[str(filepath)].add(assetpath)

    json.dump(report, sys.stdout, cls=JSONSerialiser, indent=4)
