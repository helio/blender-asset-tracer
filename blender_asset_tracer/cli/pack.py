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
"""Create a BAT-pack for the given blend file."""
import logging
import pathlib
import sys
import typing

import blender_asset_tracer.pack.transfer
from blender_asset_tracer import pack

log = logging.getLogger(__name__)


def add_parser(subparsers):
    """Add argparser for this subcommand."""

    parser = subparsers.add_parser('pack', help=__doc__)
    parser.set_defaults(func=cli_pack)
    parser.add_argument('blendfile', type=pathlib.Path,
                        help='The Blend file to pack.')
    parser.add_argument('target', type=pathlib.Path,
                        help='The target can be a directory, a ZIP file (does not have to exist '
                             "yet, just use 'something.zip' as target), or a URL of S3 storage "
                             '(s3://endpoint/path).')

    parser.add_argument('-p', '--project', type=pathlib.Path,
                        help='Root directory of your project. Paths to below this directory are '
                             'kept in the BAT Pack as well, whereas references to assets from '
                             'outside this directory will have to be rewitten. The blend file MUST '
                             'be inside the project directory. If this option is ommitted, the '
                             'directory containing the blend file is taken as the project '
                             'directoy.')
    parser.add_argument('-n', '--noop', default=False, action='store_true',
                        help="Don't copy files, just show what would be done.")
    parser.add_argument('-e', '--exclude', nargs='*', default='',
                        help="Space-separated list of glob patterns (like '*.abc *.vbo') to "
                             "exclude.")
    parser.add_argument('-c', '--compress', default=False, action='store_true',
                        help='Compress blend files while copying. This option is only valid when '
                             'packing into a directory (contrary to ZIP file or S3 upload). '
                             'Note that files will NOT be compressed when the destination file '
                             'already exists and has the same size as the original file.')
    parser.add_argument('-r', '--relative-only', default=False, action='store_true',
                        help='Only pack assets that are referred to with a relative path (e.g. '
                             'starting with `//`.')


def cli_pack(args):
    bpath, ppath, tpath = paths_from_cli(args)

    with create_packer(args, bpath, ppath, tpath) as packer:
        packer.strategise()
        try:
            packer.execute()
        except blender_asset_tracer.pack.transfer.FileTransferError as ex:
            log.error("%d files couldn't be copied, starting with %s",
                      len(ex.files_remaining), ex.files_remaining[0])
            raise SystemExit(1)


def create_packer(args, bpath: pathlib.Path, ppath: pathlib.Path,
                  tpath: pathlib.Path) -> pack.Packer:
    if str(tpath).startswith('s3:/'):
        if args.noop:
            raise ValueError('S3 uploader does not support no-op.')

        if args.compress:
            raise ValueError('S3 uploader does not support on-the-fly compression')

        if args.relative_only:
            raise ValueError('S3 uploader does not support the --relative-only option')

        packer = create_s3packer(bpath, ppath, tpath)
    elif tpath.suffix.lower() == '.zip':
        from blender_asset_tracer.pack import zipped

        if args.compress:
            raise ValueError('ZIP packer does not support on-the-fly compression')

        packer = zipped.ZipPacker(bpath, ppath, tpath, noop=args.noop,
                                  relative_only=args.relative_only)
    else:
        packer = pack.Packer(bpath, ppath, tpath, noop=args.noop, compress=args.compress,
                             relative_only=args.relative_only)

    if args.exclude:
        # args.exclude is a list, due to nargs='*', so we have to split and flatten.
        globs = [glob
                 for globs in args.exclude
                 for glob in globs.split()]
        log.info('Excluding: %s', ', '.join(repr(g) for g in globs))
        packer.exclude(*globs)
    return packer


def create_s3packer(bpath, ppath, tpath) -> pack.Packer:
    from blender_asset_tracer.pack import s3

    # Split the target path into 's3:/', hostname, and actual target path
    parts = tpath.parts
    endpoint = 'https://%s/' % parts[1]
    tpath = pathlib.Path(*tpath.parts[2:])
    log.info('Uploading to S3-compatible storage %s at %s', endpoint, tpath)

    return s3.S3Packer(bpath, ppath, tpath, endpoint=endpoint)


def paths_from_cli(args) -> typing.Tuple[pathlib.Path, pathlib.Path, pathlib.Path]:
    """Return paths to blendfile, project, and pack target.

    Calls sys.exit() if anything is wrong.
    """
    bpath = args.blendfile
    if not bpath.exists():
        log.critical('File %s does not exist', bpath)
        sys.exit(3)
    if bpath.is_dir():
        log.critical('%s is a directory, should be a blend file')
        sys.exit(3)
    bpath = bpath.absolute().resolve()

    tpath = args.target

    if args.project is None:
        ppath = bpath.absolute().parent.resolve()
        log.warning('No project path given, using %s', ppath)
    else:
        ppath = args.project.absolute().resolve()

    if not ppath.exists():
        log.critical('Project directory %s does not exist', ppath)
        sys.exit(5)

    if not ppath.is_dir():
        log.warning('Project path %s is not a directory; using the parent %s', ppath, ppath.parent)
        ppath = ppath.parent

    try:
        bpath.relative_to(ppath)
    except ValueError:
        log.critical('Project directory %s does not contain blend file %s',
                     args.project, bpath.absolute())
        sys.exit(5)

    log.info('Blend file to pack: %s', bpath)
    log.info('Project path: %s', ppath)
    log.info('Pack will be created in: %s', tpath)

    return bpath, ppath, tpath
