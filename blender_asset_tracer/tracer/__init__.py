import logging
import pathlib
import typing

from blender_asset_tracer import blendfile, bpathlib
from . import result, blocks2assets, file2blocks

log = logging.getLogger(__name__)

codes_to_skip = {
    # These blocks never have external assets:
    b'ID', b'WM', b'SN',

    # These blocks are skipped for now, until we have proof they point to
    # assets otherwise missed:
    b'GR', b'WO', b'BR', b'LS',
}


def deps(bfilepath: pathlib.Path) -> typing.Iterator[result.BlockUsage]:
    """Open the blend file and report its dependencies.

    :param bfilepath: File to open.
    """

    bfile = blendfile.open_cached(bfilepath)

    # Sort the asset-holding blocks so that we can iterate over them
    # in disk order, which is slightly faster than random order.
    ahb = asset_holding_blocks(file2blocks.iter_blocks(bfile))
    for block in sorted(ahb):
        yield from blocks2assets.iter_assets(block)


def asset_holding_blocks(blocks: typing.Iterable[blendfile.BlendFileBlock]) \
        -> typing.Iterator[blendfile.BlendFileBlock]:
    """Generator, yield data blocks that could reference external assets."""
    for block in blocks:
        assert isinstance(block, blendfile.BlendFileBlock)
        code = block.code

        # The longer codes are either arbitrary data or data blocks that
        # don't refer to external assets. The former data blocks will be
        # visited when we hit the two-letter datablocks that use them.
        if len(code) > 2 or code in codes_to_skip:
            continue

        yield block
