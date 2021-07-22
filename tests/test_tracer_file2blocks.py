from blender_asset_tracer import blendfile
from blender_asset_tracer.trace import file2blocks

from tests.test_tracer import AbstractTracerTest


class File2BlocksTest(AbstractTracerTest):
    def test_id_blocks(self):
        self.bf = blendfile.BlendFile(self.blendfiles / "doubly_linked.blend")

        foreign_blocks = {}
        for block in file2blocks.iter_blocks(self.bf):
            # Only register blocks from libraries.
            if block.bfile == self.bf:
                continue
            foreign_blocks[block.id_name] = block

        self.assertNotEqual({}, foreign_blocks)
        # It should find directly linked blocks (GRCubes and MABrick) as well
        # as indirectly linked (MECube³).
        self.assertIn(b"GRCubes", foreign_blocks)
        self.assertIn(b"MABrick", foreign_blocks)
        self.assertIn("MECube³".encode(), foreign_blocks)
        self.assertIn("OBümlaut".encode(), foreign_blocks)

    def test_circular_files(self):
        self.bf = blendfile.BlendFile(self.blendfiles / "recursive_dependency_1.blend")

        blocks = {}
        for block in file2blocks.iter_blocks(self.bf):
            blocks[block.id_name] = block

        self.assertNotEqual({}, blocks)
        self.assertIn(b"MAMaterial", blocks)
        self.assertIn(b"OBCube", blocks)
        self.assertIn(b"MECube", blocks)
