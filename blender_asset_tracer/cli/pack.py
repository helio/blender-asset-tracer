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
    parser.add_argument('blendfile', type=pathlib.Path)
    parser.add_argument('target', type=pathlib.Path)
    parser.add_argument('-p', '--project', type=pathlib.Path,
                        help='Root directory of your project. Paths to below this directory are '
                             'kept in the BAT Pack as well, whereas references to assets from '
                             'outside this directory will have to be rewitten. The blend file MUST '
                             'be inside the project directory. If this option is ommitted, the '
                             'directory containing the blend file is taken as the project '
                             'directoy.')
    parser.add_argument('-n', '--noop', default=False, action='store_true',
                        help="Don't copy files, just show what would be done.")


def cli_pack(args):
    bpath, ppath, tpath = paths_from_cli(args)

    packer = create_packer(args, bpath, ppath, tpath)
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

        from blender_asset_tracer.pack import s3

        # Split the target path into 's3:/', hostname, and actual target path
        parts = tpath.parts
        endpoint = parts[1]
        tpath = pathlib.Path(*tpath.parts[2:])
        log.info('Uploading to S3-compatible storage %s at %s', endpoint, tpath)

        return s3.S3Packer(bpath, ppath, tpath, endpoint=endpoint)

    return pack.Packer(bpath, ppath, tpath, args.noop)


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

    tpath = args.target
    if tpath.exists() and not tpath.is_dir():
        log.critical('Target %s exists and is not a directory', tpath)
        sys.exit(4)

    if args.project is None:
        ppath = bpath.absolute().parent
        log.warning('No project path given, using %s', ppath)
    else:
        ppath = args.project.absolute()

    if not ppath.exists():
        log.critical('Project directory %s does not exist', ppath)
        sys.exit(5)
    if not ppath.is_dir():
        log.warning('Project path %s is not a directory; using the parent %s', ppath, ppath.parent)
        ppath = ppath.parent

    try:
        bpath.absolute().relative_to(ppath)
    except ValueError:
        log.critical('Project directory %s does not contain blend file %s',
                     args.project, bpath.absolute())
        sys.exit(5)

    log.info('Blend file to pack: %s', bpath)
    log.info('Project path: %s', ppath)
    log.info('Pack will be created in: %s', tpath)

    return bpath, ppath, tpath
