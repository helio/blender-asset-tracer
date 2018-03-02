"""Create a BAT-pack for the given blend file."""
import functools
import logging
import pathlib
import shutil

from blender_asset_tracer import tracer
from . import common

log = logging.getLogger(__name__)


def add_parser(subparsers):
    """Add argparser for this subcommand."""

    parser = subparsers.add_parser('pack', help=__doc__)
    parser.set_defaults(func=cli_pack)
    parser.add_argument('blendfile', type=pathlib.Path)
    parser.add_argument('target', type=pathlib.Path)


def cli_pack(args):
    bpath = args.blendfile
    if not bpath.exists():
        log.fatal('File %s does not exist', args.bpath)
        return 3

    tpath = args.target
    if tpath.exists() and not tpath.is_dir():
        log.fatal('Target %s exists and is not a directory', tpath)
        return 4

    shorten = functools.partial(common.shorten, pathlib.Path.cwd())
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
            # TODO(Sybren): when we target Py 3.6+, remove the str() calls.
            print(relpath)
            shutil.copyfile(str(assetpath), str(full_target))

    log.info('Copied %d files to %s', len(already_copied), tpath)
