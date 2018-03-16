# ***** BEGIN GPL LICENSE BLOCK *****
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software Foundation,
# Inc., 59 Temple Place - Suite 330, Boston, MA  02111-1307, USA.
#
# ***** END GPL LICENCE BLOCK *****
#
# (c) 2018, Blender Foundation - Sybren A. Stüvel
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
