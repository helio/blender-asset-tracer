"""Block walkers.

From a BlendFileBlock, the block walker functions yield BlockUsage objects.
The top-level block walkers are implemented as _from_block_XX() function,
where XX is the DNA code of the block.
"""

import functools
import logging
import sys
import typing

from blender_asset_tracer import blendfile, bpathlib
from blender_asset_tracer.blendfile import iterators
from . import result, cdefs, modifier_walkers

log = logging.getLogger(__name__)

_warned_about_types = set()


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

    log.debug('Tracing block %r', block)
    yield from block_reader(block)


def skip_packed(wrapped):
    """Decorator, skip blocks where 'packedfile' is set to true."""

    @functools.wraps(wrapped)
    def wrapper(block: blendfile.BlendFileBlock, *args, **kwargs):
        if block.get(b'packedfile', default=False):
            return

        yield from wrapped(block, *args, **kwargs)

    return wrapper


def _from_block_cf(block: blendfile.BlendFileBlock) -> typing.Iterator[result.BlockUsage]:
    """Cache file data blocks."""
    path, field = block.get(b'filepath', return_field=True)
    yield result.BlockUsage(block, path, path_full_field=field)


@skip_packed
def _from_block_im(block: blendfile.BlendFileBlock) -> typing.Iterator[result.BlockUsage]:
    """Image data blocks."""
    # old files miss this
    image_source = block.get(b'source', default=cdefs.IMA_SRC_FILE)
    if image_source not in {cdefs.IMA_SRC_FILE, cdefs.IMA_SRC_SEQUENCE, cdefs.IMA_SRC_MOVIE}:
        return

    pathname, field = block.get(b'name', return_field=True)
    is_sequence = image_source == cdefs.IMA_SRC_SEQUENCE

    yield result.BlockUsage(block, pathname, is_sequence, path_full_field=field)


def _from_block_li(block: blendfile.BlendFileBlock) -> typing.Iterator[result.BlockUsage]:
    """Library data blocks."""
    path, field = block.get(b'name', return_field=True)
    yield result.BlockUsage(block, path, path_full_field=field)

    # The 'filepath' also points to the blend file. However, this is set to the
    # absolute path of the file by Blender (see BKE_library_filepath_set). This
    # is thus not a property we have to report or rewrite.


def _from_block_me(block: blendfile.BlendFileBlock) -> typing.Iterator[result.BlockUsage]:
    """Mesh data blocks."""
    block_external = block.get_pointer((b'ldata', b'external'), None)
    if block_external is None:
        block_external = block.get_pointer((b'fdata', b'external'), None)
    if block_external is None:
        return

    path, field = block_external.get(b'filename', return_field=True)
    yield result.BlockUsage(block, path, path_full_field=field)


def _from_block_mc(block: blendfile.BlendFileBlock) -> typing.Iterator[result.BlockUsage]:
    """MovieClip data blocks."""
    path, field = block.get(b'name', return_field=True)
    # TODO: The assumption that this is not a sequence may not be true for all modifiers.
    yield result.BlockUsage(block, path, is_sequence=False, path_full_field=field)


def _from_block_ob(block: blendfile.BlendFileBlock) -> typing.Iterator[result.BlockUsage]:
    """Object data blocks."""
    # 'ob->modifiers[...].filepath'
    ob_idname = block[b'id', b'name']
    mods = block.get_pointer((b'modifiers', b'first'))
    for mod_idx, block_mod in enumerate(iterators.listbase(mods, next_path=(b'modifier', b'next'))):
        block_name = b'%s.modifiers[%d]' % (ob_idname, mod_idx)
        mod_type = block_mod[b'modifier', b'type']
        log.debug('Tracing modifier %s, type=%d', block_name.decode(), mod_type)

        try:
            mod_handler = modifier_walkers.modifier_handlers[mod_type]
        except KeyError:
            continue
        yield from mod_handler(block_mod, block_name)


def _from_block_sc(block: blendfile.BlendFileBlock) -> typing.Iterator[result.BlockUsage]:
    """Scene data blocks."""
    # Sequence editor is the only interesting bit.
    block_ed = block.get_pointer(b'ed')
    if block_ed is None:
        return

    single_asset_types = {cdefs.SEQ_TYPE_MOVIE, cdefs.SEQ_TYPE_SOUND_RAM, cdefs.SEQ_TYPE_SOUND_HD}
    asset_types = single_asset_types.union({cdefs.SEQ_TYPE_IMAGE})

    def iter_seqbase(seqbase) -> typing.Iterator[result.BlockUsage]:
        """Generate results from a ListBase of sequencer strips."""

        for seq in iterators.listbase(seqbase):
            seq.refine_type(b'Sequence')
            seq_type = seq[b'type']

            if seq_type == cdefs.SEQ_TYPE_META:
                # Recurse into this meta-sequence.
                subseq = seq.get_pointer((b'seqbase', b'first'))
                yield from iter_seqbase(subseq)
                continue

            if seq_type not in asset_types:
                continue

            seq_strip = seq.get_pointer(b'strip')
            if seq_strip is None:
                continue
            seq_stripdata = seq_strip.get_pointer(b'stripdata')
            if seq_stripdata is None:
                continue

            dirname, dn_field = seq_strip.get(b'dir', return_field=True)
            basename, bn_field = seq_stripdata.get(b'name', return_field=True)
            asset_path = bpathlib.BlendPath(dirname) / basename

            is_sequence = seq_type not in single_asset_types
            yield result.BlockUsage(seq, asset_path,
                                    is_sequence=is_sequence,
                                    path_dir_field=dn_field,
                                    path_base_field=bn_field)

    sbase = block_ed.get_pointer((b'seqbase', b'first'))
    yield from iter_seqbase(sbase)


@skip_packed
def _from_block_so(block: blendfile.BlendFileBlock) -> typing.Iterator[result.BlockUsage]:
    """Sound data blocks."""
    path, field = block.get(b'name', return_field=True)
    yield result.BlockUsage(block, path, path_full_field=field)


@skip_packed
def _from_block_vf(block: blendfile.BlendFileBlock) -> typing.Iterator[result.BlockUsage]:
    """Vector Font data blocks."""
    path, field = block.get(b'name', return_field=True)
    if path == b'<builtin>':  # builtin font
        return
    yield result.BlockUsage(block, path, path_full_field=field)
