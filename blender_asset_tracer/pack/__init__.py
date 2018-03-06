import functools
import logging
import pathlib
import shutil

from blender_asset_tracer import tracer
from blender_asset_tracer.cli import common

log = logging.getLogger(__name__)


class Packer:
    def __init__(self,
                 blendfile: pathlib.Path,
                 project: pathlib.Path,
                 target: pathlib.Path,
                 noop: bool):
        self.blendfile = blendfile
        self.project = project
        self.target = target
        self.noop = noop

        self._already_copied = set()
        self._shorten = functools.partial(common.shorten, self.project)

        if noop:
            log.warning('Running in no-op mode, only showing what will be done.')

    def investigate(self):
        pass

    def pack(self):
        for usage in tracer.deps(self.blendfile):
            if usage.asset_path.is_absolute():
                raise NotImplementedError('Sorry, cannot handle absolute paths yet: %s' % usage)

            for assetpath in usage.files():
                self._copy_to_target(assetpath)

        log.info('Copied %d files to %s', len(self._already_copied), self.target)

    def _copy_to_target(self, assetpath: pathlib.Path):
        try:
            assetpath = assetpath.resolve()
        except FileNotFoundError:
            log.error('Dependency %s does not exist', assetpath)

        if assetpath in self._already_copied:
            log.debug('Already copied %s', assetpath)
            return
        self._already_copied.add(assetpath)

        relpath = self._shorten(assetpath)
        if relpath.is_absolute():
            raise NotImplementedError(
                'Sorry, cannot handle paths outside project directory yet: %s is not in %s'
                % (relpath, self.project))

        full_target = self.target / relpath
        full_target.parent.mkdir(parents=True, exist_ok=True)
        if self.noop:
            print('%s → %s' % (assetpath, full_target))
        else:
            print(relpath)
            # TODO(Sybren): when we target Py 3.6+, remove the str() calls.
            shutil.copyfile(str(assetpath), str(full_target))
