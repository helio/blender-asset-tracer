import logging
import sys
import typing

from blender_asset_tracer import blendfile
from . import result, cdefs

log = logging.getLogger(__name__)

_warned_about_types = set()


class NoReaderImplemented(NotImplementedError):
    """There is no reader implementation for a specific block code."""

    def __init__(self, message: str, code: bytes):
        super().__init__(message)
        self.code = code


def from_block(block: blendfile.BlendFileBlock) -> typing.Iterator[result.BlockUsage]:
    assert block.code != b'DATA'

    module = sys.modules[__name__]
    funcname = '_from_block_' + block.code.decode().lower()
    try:
        block_reader = getattr(module, funcname)
    except AttributeError:
        if block.code not in _warned_about_types:
            log.warning('No reader implemented for block type %r', block.code.decode())
            _warned_about_types.add(block.code)
        return

    yield from block_reader(block)


def _from_block_im(block: blendfile.BlendFileBlock) -> typing.Iterator[result.BlockUsage]:
    # old files miss this
    image_source = block.get(b'source', default=cdefs.IMA_SRC_FILE)
    if image_source not in {cdefs.IMA_SRC_FILE, cdefs.IMA_SRC_SEQUENCE, cdefs.IMA_SRC_MOVIE}:
        return
    if block[b'packedfile']:
        return

    pathname, field = block.get(b'name', return_field=True)

    # TODO: the receiver should inspect the 'source' property too, and if set
    # to cdefs.IMA_SRC_SEQUENCE yield the entire sequence of files.
    yield result.BlockUsage(block, field, pathname)
