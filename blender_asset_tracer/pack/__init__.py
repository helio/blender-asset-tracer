import collections
import enum
import functools
import logging
import pathlib
import tempfile
import typing

from blender_asset_tracer import trace, bpathlib, blendfile
from blender_asset_tracer.trace import result
from . import filesystem, transfer

log = logging.getLogger(__name__)


class PathAction(enum.Enum):
    KEEP_PATH = 1
    FIND_NEW_LOCATION = 2


class AssetAction:
    """All the info required to rewrite blend files and copy assets."""

    def __init__(self) -> None:
        self.path_action = PathAction.KEEP_PATH
        self.usages = []  # type: typing.List[result.BlockUsage]
        """BlockUsage objects referring to this asset.

        Those BlockUsage objects could refer to data blocks in this blend file
        (if the asset is a blend file) or in another blend file.
        """

        self.new_path = None  # type: pathlib.Path
        """Absolute path to the asset in the BAT Pack.

        This path may not exist on the local file system at all, for example
        when uploading files to remote S3-compatible storage.
        """

        self.read_from = None  # type: typing.Optional[pathlib.Path]
        """Optional path from which to read the asset.

        This is used when blend files have been rewritten. It is assumed that
        when this property is set, the file can be moved instead of copied.
        """

        self.rewrites = []  # type: typing.List[result.BlockUsage]
        """BlockUsage objects in this asset that may require rewriting.

        Empty list if this AssetAction is not for a blend file.
        """


class Packer:
    def __init__(self,
                 blendfile: pathlib.Path,
                 project: pathlib.Path,
                 target: pathlib.Path,
                 noop=False) -> None:
        self.blendfile = blendfile
        self.project = project
        self.target = target
        self.noop = noop

        self._exclude_globs = set()  # type: typing.Set[str]

        from blender_asset_tracer.cli import common
        self._shorten = functools.partial(common.shorten, self.project)

        if noop:
            log.warning('Running in no-op mode, only showing what will be done.')

        # Filled by strategise()
        self._actions = collections.defaultdict(AssetAction) \
            # type: typing.DefaultDict[pathlib.Path, AssetAction]
        self.missing_files = set()  # type: typing.Set[pathlib.Path]
        self._output_path = None  # type: pathlib.Path

        # Number of files we would copy, if not for --noop
        self._file_count = 0

        self._tmpdir = tempfile.TemporaryDirectory(suffix='-batpack')
        self._rewrite_in = pathlib.Path(self._tmpdir.name)

    def close(self) -> None:
        """Clean up any temporary files."""
        self._tmpdir.cleanup()

    def __enter__(self) -> 'Packer':
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()

    @property
    def output_path(self) -> pathlib.Path:
        """The path of the packed blend file in the target directory."""
        return self._output_path

    def exclude(self, *globs: str):
        """Register glob-compatible patterns of files that should be ignored."""
        self._exclude_globs.update(globs)

    def strategise(self) -> None:
        """Determine what to do with the assets.

        Places an asset into one of these categories:
            - Can be copied as-is, nothing smart required.
            - Blend files referring to this asset need to be rewritten.
        """

        # The blendfile that we pack is generally not its own dependency, so
        # we have to explicitly add it to the _packed_paths.
        bfile_path = self.blendfile.absolute()
        bfile_pp = self.target / bfile_path.relative_to(self.project)
        self._output_path = bfile_pp

        act = self._actions[bfile_path]
        act.path_action = PathAction.KEEP_PATH
        act.new_path = bfile_pp

        new_location_paths = set()
        for usage in trace.deps(self.blendfile):
            asset_path = usage.abspath
            if any(asset_path.match(glob) for glob in self._exclude_globs):
                log.info('Excluding file: %s', asset_path)
                continue

            if not asset_path.exists():
                log.info('Missing file: %s', asset_path)
                self.missing_files.add(asset_path)
                continue

            bfile_path = usage.block.bfile.filepath.absolute()

            # Needing rewriting is not a per-asset thing, but a per-asset-per-
            # blendfile thing, since different blendfiles can refer to it in
            # different ways (for example with relative and absolute paths).
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
                log.debug('%s can keep using %s', bfile_path, usage.asset_path)
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

    def _group_rewrites(self) -> None:
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
                self._actions[bfile_path].rewrites.append(usage)

    def _path_in_project(self, path: pathlib.Path) -> bool:
        try:
            # MUST use resolve(), otherwise /path/to/proj/../../asset.png
            # will return True (relative_to will return ../../asset.png).
            path.resolve().relative_to(self.project)
        except ValueError:
            return False
        return True

    def execute(self) -> None:
        """Execute the strategy."""
        assert self._actions, 'Run strategise() first'

        if not self.noop:
            self._rewrite_paths()
        self._copy_files_to_target()

    def _create_file_transferer(self) -> transfer.FileTransferer:
        """Create a FileCopier(), can be overridden in a subclass."""
        return filesystem.FileCopier()

    def _copy_files_to_target(self) -> None:
        """Copy all assets to the target directoy.

        This creates the BAT Pack but does not yet do any path rewriting.
        """
        log.debug('Executing %d copy actions', len(self._actions))

        ft = self._create_file_transferer()
        if not self.noop:
            ft.start()

        try:
            for asset_path, action in self._actions.items():
                self._copy_asset_and_deps(asset_path, action, ft)

            if self.noop:
                log.info('Would copy %d files to %s', self._file_count, self.target)
                return
            ft.done_and_join()
        except KeyboardInterrupt:
            log.info('File transfer interrupted with Ctrl+C, aborting.')
            ft.abort_and_join()
            raise

    def _rewrite_paths(self) -> None:
        """Rewrite paths to the new location of the assets.

        Writes the rewritten blend files to a temporary location.
        """

        for bfile_path, action in self._actions.items():
            if not action.rewrites:
                continue

            assert isinstance(bfile_path, pathlib.Path)
            # bfile_pp is the final path of this blend file in the BAT pack.
            # It is used to determine relative paths to other blend files.
            # It is *not* used for any disk I/O, since the file may not even
            # exist on the local filesystem.
            bfile_pp = self._actions[bfile_path].new_path

            # Use tempfile to create a unique name in our temporary directoy.
            # The file should be deleted when self.close() is called, and not
            # when the bfile_tp object is GC'd.
            bfile_tmp = tempfile.NamedTemporaryFile(dir=str(self._rewrite_in),
                                                    suffix='-' + bfile_path.name,
                                                    delete=False)
            bfile_tp = pathlib.Path(bfile_tmp.name)
            action.read_from = bfile_tp
            log.info('Rewriting %s to %s', bfile_path, bfile_tp)

            # The original blend file will have been cached, so we can use it
            # to avoid re-parsing all data blocks in the to-be-rewritten file.
            bfile = blendfile.open_cached(bfile_path, assert_cached=True)
            bfile.copy_and_rebind(bfile_tp, mode='rb+')

            for usage in action.rewrites:
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
                    log.debug('   - updating field %s of block %s',
                              usage.path_dir_field.name.name_only, block)
                    reldir = bpathlib.BlendPath.mkrelative(asset_pp.parent, bfile_pp)
                    written = block.set(usage.path_dir_field.name.name_only, reldir)
                    log.debug('   - written %d bytes', written)

                    # BIG FAT ASSUMPTION that the filename (e.g. basename
                    # without path) does not change. This makes things much
                    # easier, as in the sequence editor the directory and
                    # filename fields are in different blocks. See the
                    # blocks2assets.scene() function for the implementation.
                else:
                    log.debug('   - updating field %s of block %s',
                              usage.path_full_field.name.name_only, block)
                    written = block.set(usage.path_full_field.name.name_only, relpath)
                    log.debug('   - written %d bytes', written)

            # Make sure we close the file, otherwise changes may not be
            # flushed before it gets copied.
            bfile.close()

    def _copy_asset_and_deps(self, asset_path: pathlib.Path, action: AssetAction,
                             ft: transfer.FileTransferer):
        # Copy the asset itself.
        packed_path = action.new_path
        read_path = action.read_from or asset_path
        self._send_to_target(read_path, packed_path, ft,
                             may_move=action.read_from is not None)

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
                # Assumption: assets in a sequence are never blend files.
                self._send_to_target(file_path, packed_path, ft)

            # Assumption: all data blocks using this asset use it the same way.
            break

    def _send_to_target(self,
                        asset_path: pathlib.Path,
                        target: pathlib.Path,
                        ft: transfer.FileTransferer,
                        may_move=False):
        if self.noop:
            print('%s → %s' % (asset_path, target))
            self._file_count += 1
            return

        verb = 'move' if may_move else 'copy'
        log.debug('Queueing %s of %s', verb, asset_path)

        if may_move:
            ft.queue_move(asset_path, target)
        else:
            ft.queue_copy(asset_path, target)
