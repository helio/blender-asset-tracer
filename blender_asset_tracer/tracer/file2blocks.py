"""Expand data blocks.

The expansion process follows pointers and library links to construct the full
set of actually-used data blocks. This set consists of all data blocks in the
initial blend file, and all *actually linked-to* data blocks in linked
blend files.
"""
import collections
import logging
import typing

from blender_asset_tracer import blendfile, bpathlib
from . import expanders

_funcs_for_code = {}
log = logging.getLogger(__name__)


class _BlockIterator:
    """Expand blocks with dependencies from other libraries.

    This class exists so that we have some context for the recursive expansion
    without having to pass those variables to each recursive call.
    """

    def __init__(self):
        # Set of (blend file Path, block address) of already-reported blocks.
        self.blocks_yielded = set()

        # Queue of blocks to visit
        self.to_visit = collections.deque()

    def iter_blocks(self,
                    bfile: blendfile.BlendFile,
                    limit_to: typing.Set[blendfile.BlendFileBlock] = frozenset(),
                    ) -> typing.Iterator[blendfile.BlendFileBlock]:
        """Expand blocks with dependencies from other libraries."""
        bpath = bfile.filepath.absolute().resolve()
        root_dir = bpathlib.BlendPath(bpath.parent)

        # Mapping from library path to data blocks to expand.
        blocks_per_lib = collections.defaultdict(set)

        if limit_to:
            self._queue_named_blocks(bfile, limit_to)
        else:
            self._queue_all_blocks(bfile)

        while self.to_visit:
            block = self.to_visit.popleft()
            assert isinstance(block, blendfile.BlendFileBlock)
            if (bpath, block.addr_old) in self.blocks_yielded:
                continue

            if block.code == b'ID':
                # ID blocks represent linked-in assets. Those are the ones that
                # should be loaded from their own blend file and "expanded" to
                # the entire set of data blocks required to render them. We
                # defer the handling of those so that we can work with one
                # blend file at a time.
                lib = block.get_pointer(b'lib')
                lib_bpath = bpathlib.BlendPath(lib[b'name']).absolute(root_dir)
                blocks_per_lib[lib_bpath].add(block)

                # The library block itself should also be reported, because it
                # represents a blend file that is a dependency as well.
                self.to_visit.append(lib)
                continue

            if limit_to:
                # We're limiting the blocks, so we have to expand them to make
                # sure we don't miss anything. Otherwise we're yielding the
                # entire file anyway, and no expansion is necessary.
                self._queue_dependencies(block)
            self.blocks_yielded.add((bpath, block.addr_old))
            yield block

        # We've gone through all the blocks in this file, now open the libraries
        # and iterate over the blocks referred there.
        for lib_bpath, idblocks in blocks_per_lib.items():
            lib_path = lib_bpath.to_path()
            try:
                lib_path = lib_path.resolve()
            except FileNotFoundError:
                log.warning('Library %s does not exist', lib_path)
                continue

            log.debug('Expanding %d blocks in %s', len(idblocks), lib_path)

            with blendfile.BlendFile(lib_path) as libfile:
                yield from self.iter_blocks(libfile, idblocks)

    def _queue_all_blocks(self, bfile: blendfile.BlendFile):
        log.debug('Queueing all blocks from file %s', bfile.filepath)
        # Don't bother visiting DATA blocks, as we won't know what
        # to do with them anyway.
        self.to_visit.extend(block for block in bfile.blocks
                             if block.code != b'DATA')

    def _queue_named_blocks(self,
                            bfile: blendfile.BlendFile,
                            limit_to: typing.Set[blendfile.BlendFileBlock]):
        """Queue only the blocks referred to in limit_to.

        :param bfile:
        :param limit_to: set of ID blocks that name the blocks to queue.
            The queued blocks are loaded from the actual blend file, and
            selected by name.
        """
        for to_find in limit_to:
            assert to_find.code == b'ID'
            name_to_find = to_find[b'name']
            code = name_to_find[:2]
            log.debug('Finding block %r with code %r', name_to_find, code)
            same_code = bfile.find_blocks_from_code(code)
            for block in same_code:
                if block.id_name == name_to_find:
                    log.debug('Queueing %r from file %s', block, bfile.filepath)
                    self.to_visit.append(block)

    def _queue_dependencies(self, block: blendfile.BlendFileBlock):
        self.to_visit.extend(expanders.expand_block(block))


def iter_blocks(bfile: blendfile.BlendFile) -> typing.Iterator[blendfile.BlendFileBlock]:
    """Generator, yield all blocks in this file + required blocks in libs."""
    bi = _BlockIterator()
    yield from bi.iter_blocks(bfile)