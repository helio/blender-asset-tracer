from . import BlendFileBlock
from .dna import FieldPath


def listbase(block: BlendFileBlock, next_path: FieldPath=b'next') -> BlendFileBlock:
    """Generator, yields all blocks in the ListBase linked list."""
    while block:
        yield block
        next_ptr = block[next_path]
        block = block.bfile.find_block_from_address(next_ptr)
