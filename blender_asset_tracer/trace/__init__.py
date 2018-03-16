import logging
import pathlib
import typing

from blender_asset_tracer import blendfile
from . import result, blocks2assets, file2blocks, progress

log = logging.getLogger(__name__)

codes_to_skip = {
    # These blocks never have external assets:
    b'ID', b'WM', b'SN',

    # These blocks are skipped for now, until we have proof they point to
    # assets otherwise missed:
    b'GR', b'WO', b'BR', b'LS',
}


def deps(bfilepath: pathlib.Path, progress_cb: typing.Optional[progress.Callback] = None) \
        -> typing.Iterator[result.BlockUsage]:
    """Open the blend file and report its dependencies.

    :param bfilepath: File to open.
    :param progress_cb: Progress callback object.
    """

    log.info('opening: %s', bfilepath)
    bfile = blendfile.open_cached(bfilepath)

    bi = file2blocks.BlockIterator()
    if progress_cb:
        bi.progress_cb = progress_cb

    for block in asset_holding_blocks(bi.iter_blocks(bfile)):
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
