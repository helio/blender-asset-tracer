import logging
import pathlib
import typing

from blender_asset_tracer import blendfile
from . import result, block_walkers

log = logging.getLogger(__name__)

codes_to_skip = {
    b'ID', b'WM', b'SN',  # These blocks never have external assets.
}


def deps(bfilepath: pathlib.Path) -> typing.Iterator[result.BlockUsage]:
    """Open the blend file and report its dependencies."""
    log.info('Tracing %s', bfilepath)

    with blendfile.BlendFile(bfilepath) as bfile:
        for block in asset_holding_blocks(bfile):
            yield from block_walkers.from_block(block)

        # TODO: handle library blocks for recursion.


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
