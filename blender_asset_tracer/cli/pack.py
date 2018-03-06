"""Create a BAT-pack for the given blend file."""
import functools
import logging
import pathlib
import shutil
import sys

from blender_asset_tracer import tracer
from . import common

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
    if args.noop:
        log.warning('Running in no-op mode, only showing what will be done.')

    shorten = functools.partial(common.shorten, ppath)
    already_copied = set()
    for usage in tracer.deps(bpath):
        if usage.asset_path.is_absolute():
            raise NotImplementedError('Sorry, cannot handle absolute paths yet: %s' % usage)

        for assetpath in usage.files():
            try:
                assetpath = assetpath.resolve()
            except FileNotFoundError:
                log.error('Dependency %s does not exist', assetpath)

            if assetpath in already_copied:
                log.debug('Already copied %s', assetpath)
                continue
            already_copied.add(assetpath)

            relpath = shorten(assetpath)
            if relpath.is_absolute():
                raise NotImplementedError('Sorry, cannot handle absolute paths yet: %s in %s'
                                          % (usage, assetpath))

            full_target = tpath / relpath
            full_target.parent.mkdir(parents=True, exist_ok=True)
            if args.noop:
                print('%s → %s' % (assetpath, full_target))
            else:
                print(relpath)
                # TODO(Sybren): when we target Py 3.6+, remove the str() calls.
                shutil.copyfile(str(assetpath), str(full_target))

    log.info('Copied %d files to %s', len(already_copied), tpath)


def paths_from_cli(args) -> (pathlib.Path, pathlib.Path, pathlib.Path):
    """Return paths to blendfile, project, and pack target.

    Calls sys.exit() if anything is wrong.
    """
    bpath = args.blendfile
    if not bpath.exists():
        log.critical('File %s does not exist', bpath)
        sys.exit(3)

    tpath = args.target
    if tpath.exists() and not tpath.is_dir():
        log.critical('Target %s exists and is not a directory', tpath)
        sys.exit(4)

    if args.project is None:
        ppath = bpath.absolute().parent
        log.warning('No project path given, using %s', ppath)
    else:
        ppath = args.project

    if not ppath.exists():
        log.critical('Project directory %s does not exist', ppath)
        sys.exit(5)
    try:
        bpath.absolute().relative_to(ppath)
    except ValueError:
        log.critical('Project directory %s does not contain blend file %s',
                     args.project, bpath.absolute())
        sys.exit(5)
    return bpath, ppath, tpath
