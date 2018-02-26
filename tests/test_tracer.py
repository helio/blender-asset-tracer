import logging

from abstract_test import AbstractBlendFileTest

from blender_asset_tracer import tracer, blendfile


class AbstractTracerTest(AbstractBlendFileTest):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        logging.basicConfig(level=logging.INFO)
        logging.getLogger('blender_asset_tracer.tracer').setLevel(logging.DEBUG)


class AssetHoldingBlocksTest(AbstractTracerTest):
    def setUp(self):
        self.bf = blendfile.BlendFile(self.blendfiles / 'basic_file.blend')

    def test_simple_file(self):
        # This file should not depend on external assets.
        blocks_seen = 0
        seen_scene = seen_ob = False

        for block in tracer.asset_holding_blocks(self.bf):
            assert isinstance(block, blendfile.BlendFileBlock)
            blocks_seen += 1

            # The four-letter-code blocks don't refer to assets, so they
            # shouldn't be yielded.
            self.assertEqual(2, len(block.code))

            # Library blocks should not be yielded either.
            self.assertNotEqual(b'LI', block.code)

            # Do some arbitrary tests that convince us stuff is read well.
            if block.code == b'SC':
                seen_scene = True
                self.assertEqual(b'SCScene', block[b'id', b'name'])
                continue

            if block.code == b'OB':
                seen_ob = True
                self.assertEqual('OBümlaut', block.get((b'id', b'name'), as_str=True))
                continue

        self.assertTrue(seen_scene)
        self.assertTrue(seen_ob)

        # Many of the data blocks are skipped, because asset_holding_blocks() only
        # yields top-level, directly-understandable blocks.
        #
        # The numbers here are taken from whatever the code does now; I didn't
        # count the actual blocks in the actual blend file.
        self.assertEqual(965, len(self.bf.blocks))
        self.assertEqual(37, blocks_seen)


class DepsTest(AbstractBlendFileTest):
    def test_no_deps(self):
        for dep in tracer.deps(self.blendfiles / 'basic_file.blend'):
            self.fail(dep)

    def test_ob_mat_texture(self):
        for dep in tracer.deps(self.blendfiles / 'material_textures.blend'):
            self.fail(repr(dep))
