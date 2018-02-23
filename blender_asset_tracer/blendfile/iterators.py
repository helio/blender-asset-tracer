from . import BlendFileBlock


def listbase(block: BlendFileBlock) -> BlendFileBlock:
    """Generator, yields all blocks in the ListBase linked list."""
    while block:
        yield block
        next_ptr = block[b'next']
        block = block.bfile.find_block_from_address(next_ptr)
