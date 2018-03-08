import collections
import enum
import functools
import logging
import threading
import pathlib
import queue
import shutil
import typing

from blender_asset_tracer import tracer, bpathlib, blendfile
from blender_asset_tracer.cli import common
from blender_asset_tracer.tracer import result

log = logging.getLogger(__name__)

# For copying in a different process. By using a priority queue the files
# are automatically sorted alphabetically, which means we go through all files
# in a single directory at a time. This should be faster to copy than random
# access. The order isn't guaranteed, though, as we're not waiting around for
# all file paths to be known before copying starts.
file_copy_queue = queue.PriorityQueue()
file_copy_done = threading.Event()


class FileCopyError(IOError):
    """Raised when one or more files could not be copied."""

    def __init__(self, message, files_not_copied: typing.List[pathlib.Path]):
        super().__init__(message)
        self.files_not_copied = files_not_copied


class PathAction(enum.Enum):
    KEEP_PATH = 1
    FIND_NEW_LOCATION = 2


class AssetAction:
    def __init__(self):
        self.path_action = PathAction.KEEP_PATH
        self.usages = []  # which data blocks are referring to this asset
        self.new_path = None


class Packer:
    def __init__(self,
                 blendfile: pathlib.Path,
                 project: pathlib.Path,
                 target: pathlib.Path,
                 noop=False):
        self.blendfile = blendfile
        self.project = project
        self.target = target
        self.noop = noop

        self._already_copied = set()
        self._shorten = functools.partial(common.shorten, self.project)

        if noop:
            log.warning('Running in no-op mode, only showing what will be done.')

        # Filled by strategise()
        self._actions = collections.defaultdict(AssetAction)
        self._rewrites = collections.defaultdict(list)

    def strategise(self):
        """Determine what to do with the assets.

        Places an asset into one of these categories:
            - Can be copied as-is, nothing smart required.
            - Blend files referring to this asset need to be rewritten.
        """

        # The blendfile that we pack is generally not its own dependency, so
        # we have to explicitly add it to the _packed_paths.
        bfile_path = self.blendfile.absolute()
        bfile_pp = self.target / bfile_path.relative_to(self.project)

        act = self._actions[bfile_path]
        act.path_action = PathAction.KEEP_PATH
        act.new_path = bfile_pp

        new_location_paths = set()
        for usage in tracer.deps(self.blendfile):
            # Needing rewriting is not a per-asset thing, but a per-asset-per-
            # blendfile thing, since different blendfiles can refer to it in
            # different ways (for example with relative and absolute paths).
            asset_path = usage.abspath
            bfile_path = usage.block.bfile.filepath.absolute()

            path_in_project = self._path_in_project(asset_path)
            use_as_is = usage.asset_path.is_blendfile_relative() and path_in_project
            needs_rewriting = not use_as_is

            act = self._actions[asset_path]
            assert isinstance(act, AssetAction)

            act.usages.append(usage)
            if needs_rewriting:
                log.info('%s needs rewritten path to %s', bfile_path, usage.asset_path)
                act.path_action = PathAction.FIND_NEW_LOCATION
                new_location_paths.add(asset_path)
            else:
                log.info('%s can keep using %s', bfile_path, usage.asset_path)
                asset_pp = self.target / asset_path.relative_to(self.project)
                act.new_path = asset_pp

        self._find_new_paths(new_location_paths)
        self._group_rewrites()

    def _find_new_paths(self, asset_paths: typing.Set[pathlib.Path]):
        """Find new locations in the BAT Pack for the given assets."""

        for path in asset_paths:
            act = self._actions[path]
            assert isinstance(act, AssetAction)
            # Like a join, but ignoring the fact that 'path' is absolute.
            act.new_path = pathlib.Path(self.target, '_outside_project', *path.parts[1:])

    def _group_rewrites(self):
        """For each blend file, collect which fields need rewriting.

        This ensures that the execute() step has to visit each blend file
        only once.
        """

        for action in self._actions.values():
            if action.path_action != PathAction.FIND_NEW_LOCATION:
                # This asset doesn't require a new location, so no rewriting necessary.
                continue

            for usage in action.usages:
                bfile_path = usage.block.bfile.filepath.absolute().resolve()
                self._rewrites[bfile_path].append(usage)

    def _path_in_project(self, path: pathlib.Path) -> bool:
        try:
            # MUST use resolve(), otherwise /path/to/proj/../../asset.png
            # will return True (relative_to will return ../../asset.png).
            path.resolve().relative_to(self.project)
        except ValueError:
            return False
        return True

    def execute(self):
        """Execute the strategy."""
        assert self._actions, 'Run strategise() first'

        self._copy_files_to_target()
        if not self.noop:
            self._rewrite_paths()

    def _copy_files_to_target(self):
        """Copy all assets to the target directoy.

        This creates the BAT Pack but does not yet do any path rewriting.
        """
        log.info('Executing %d copy actions', len(self._actions))

        t = threading.Thread(target=copy_queued)
        if not self.noop:
            t.start()

        for asset_path, action in self._actions.items():
            self._copy_asset_and_deps(asset_path, action)

        if self.noop:
            log.info('Would copy %d files to %s', len(self._already_copied), self.target)
            return

        file_copy_done.set()
        t.join()

        if not file_copy_queue.empty():
            # Flush the queue so that we can report which files weren't copied yet.
            files_remaining = []
            while not file_copy_queue.empty():
                src, dst = file_copy_queue.get_nowait()
                files_remaining.append(src)
            assert files_remaining
            raise FileCopyError("%d files couldn't be copied" % len(files_remaining),
                                files_remaining)

    def _rewrite_paths(self):
        """Rewrite paths to the new location of the assets."""

        for bfile_path, rewrites in self._rewrites.items():
            assert isinstance(bfile_path, pathlib.Path)
            bfile_pp = self._actions[bfile_path].new_path

            log.info('Rewriting %s', bfile_pp)

            # The original blend file will have been cached, so we can use it
            # to avoid re-parsing all data blocks in the to-be-rewritten file.
            bfile = blendfile.open_cached(bfile_path, assert_cached=True)
            bfile.rebind(bfile_pp, mode='rb+')

            for usage in rewrites:
                assert isinstance(usage, result.BlockUsage)
                asset_pp = self._actions[usage.abspath].new_path
                assert isinstance(asset_pp, pathlib.Path)

                log.debug('   - %s is packed at %s', usage.asset_path, asset_pp)
                relpath = bpathlib.BlendPath.mkrelative(asset_pp, bfile_pp)
                if relpath == usage.asset_path:
                    log.info('   - %s remained at %s', usage.asset_path, relpath)
                    continue

                log.info('   - %s moved to %s', usage.asset_path, relpath)

                # Find the same block in the newly copied file.
                block = bfile.dereference_pointer(usage.block.addr_old)
                if usage.path_full_field is None:
                    log.info('   - updating field %s of block %s',
                             usage.path_dir_field.name.name_only, block)
                    reldir = bpathlib.BlendPath.mkrelative(asset_pp.parent, bfile_pp)
                    written = block.set(usage.path_dir_field.name.name_only, reldir)
                    log.info('   - written %d bytes', written)

                    # BIG FAT ASSUMPTION that the filename (e.g. basename
                    # without path) does not change. This makes things much
                    # easier, as in the sequence editor the directory and
                    # filename fields are in different blocks. See the
                    # blocks2assets.scene() function for the implementation.
                else:
                    log.info('   - updating field %s of block %s',
                             usage.path_full_field.name.name_only, block)
                    written = block.set(usage.path_full_field.name.name_only, relpath)
                    log.info('   - written %d bytes', written)

    def _copy_asset_and_deps(self, asset_path: pathlib.Path, action: AssetAction):
        log.debug('Queueing copy of %s and dependencies', asset_path)

        # Copy the asset itself.
        packed_path = self._actions[asset_path].new_path
        self._copy_to_target(asset_path, packed_path)

        # Copy its sequence dependencies.
        for usage in action.usages:
            if not usage.is_sequence:
                continue

            first_pp = self._actions[usage.abspath].new_path

            # In case of globbing, we only support globbing by filename,
            # and not by directory.
            assert '*' not in str(first_pp) or '*' in first_pp.name

            packed_base_dir = first_pp.parent
            for file_path in usage.files():
                packed_path = packed_base_dir / file_path.name
                self._copy_to_target(file_path, packed_path)

            # Assumption: all data blocks using this asset use it the same way.
            break

    def _copy_to_target(self, asset_path: pathlib.Path, target: pathlib.Path):
        if self.noop:
            print('%s → %s' % (asset_path, target))
            return
        file_copy_queue.put((asset_path, target))


def copy_queued():
    my_log = log.getChild('copy_queued')
    files_copied = 0
    files_skipped = 0

    while True:
        try:
            src, dst = file_copy_queue.get(timeout=0.1)
        except queue.Empty:
            if file_copy_done.is_set():
                break
            continue

        try:
            if dst.exists():
                st_src = src.stat()
                st_dst = dst.stat()
                if st_dst.st_size == st_src.st_size and st_dst.st_mtime >= st_src.st_mtime:
                    my_log.info('Skipping %s; already exists', src)
                    files_skipped += 1
                    continue

            my_log.info('Copying %s → %s', src, dst)
            dst.parent.mkdir(parents=True, exist_ok=True)
            # TODO(Sybren): when we target Py 3.6+, remove the str() calls.
            shutil.copy(str(src), str(dst))
            files_copied += 1
        except Exception:
            # We have to catch exceptions in a broad way, as this is running in
            # a separate thread, and exceptions won't otherwise be seen.
            my_log.exception('Error copying %s to %s', src, dst)
            # Put the files to copy back into the queue, and abort. This allows
            # the main thread to inspect the queue and see which files were not
            # copied. The one we just failed (due to this exception) should also
            # be reported there.
            file_copy_queue.put((src, dst))
            return

    if files_copied:
        my_log.info('Copied %d files', files_copied)
    if files_skipped:
        my_log.info('Skipped %d files', files_skipped)
