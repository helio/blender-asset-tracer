import logging
import pathlib
import typing

from blender_asset_tracer import blendfile, bpathlib
from . import result, block_walkers

log = logging.getLogger(__name__)

codes_to_skip = {
    # These blocks never have external assets:
    b'ID', b'WM', b'SN',

    # These blocks are skipped for now, until we have proof they point to
    # assets otherwise missed:
    b'GR', b'WO', b'BR', b'LS',
}


def deps(bfilepath: pathlib.Path, recursive=False) -> typing.Iterator[result.BlockUsage]:
    """Open the blend file and report its dependencies.

    :param bfilepath: File to open.
    :param recursive: Also report dependencies inside linked blend files.
    """
    log.info('Tracing %s', bfilepath)

    with blendfile.BlendFile(bfilepath) as bfile:
        for block in asset_holding_blocks(bfile):
            yield from block_walkers.from_block(block)

            if recursive and block.code == b'LI':
                yield from _recurse_deps(block)


def _recurse_deps(lib_block: blendfile.BlendFileBlock) -> typing.Iterator[result.BlockUsage]:
    """Call deps() on the file linked from the library block."""
    if lib_block.code != b'LI':
        raise ValueError('Expected LI block, not %r' % lib_block)

    relpath = bpathlib.BlendPath(lib_block[b'name'])
    abspath = lib_block.bfile.abspath(relpath)

    # Convert bytes to pathlib.Path object so we have a nice interface to work with.
    # This assumes the path is encoded in UTF-8.
    path = pathlib.Path(abspath.decode())
    if not path.exists():
        log.warning('Linked blend file %s (%s) does not exist; skipping.', relpath, path)
        return

    yield from deps(path, recursive=True)


def asset_holding_blocks(bfile: blendfile.BlendFile) -> typing.Iterator[blendfile.BlendFileBlock]:
    """Generator, yield data blocks that could reference external assets."""
    for block in bfile.blocks:
        assert isinstance(block, blendfile.BlendFileBlock)
        code = block.code

        # The longer codes are either arbitrary data or data blocks that
        # don't refer to external assets. The former data blocks will be
        # visited when we hit the two-letter datablocks that use them.
        if len(code) > 2 or code in codes_to_skip:
            continue

        yield block
