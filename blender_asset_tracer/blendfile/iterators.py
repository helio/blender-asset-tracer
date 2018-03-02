import typing

from blender_asset_tracer import cdefs
from . import BlendFileBlock
from .dna import FieldPath


def listbase(block: BlendFileBlock, next_path: FieldPath = b'next') \
        -> typing.Iterator[BlendFileBlock]:
    """Generator, yields all blocks in the ListBase linked list."""
    while block:
        yield block
        next_ptr = block[next_path]
        block = block.bfile.find_block_from_address(next_ptr)


def sequencer_strips(sequence_editor: BlendFileBlock) \
        -> typing.Iterator[typing.Tuple[BlendFileBlock, int]]:
    """Generator, yield all sequencer strip blocks with their type number.

    Recurses into meta strips, yielding both the meta strip itself and the
    strips contained within it.

    See blender_asset_tracer.cdefs.SEQ_TYPE_xxx for the type numbers.
    """

    def iter_seqbase(seqbase) -> typing.Iterator[BlendFileBlock]:
        for seq in listbase(seqbase):
            seq.refine_type(b'Sequence')
            seq_type = seq[b'type']
            yield seq, seq_type

            if seq_type == cdefs.SEQ_TYPE_META:
                # Recurse into this meta-sequence.
                subseq = seq.get_pointer((b'seqbase', b'first'))
                yield from iter_seqbase(subseq)

    sbase = sequence_editor.get_pointer((b'seqbase', b'first'))
    yield from iter_seqbase(sbase)
