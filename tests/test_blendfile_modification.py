from shutil import copyfile

import os

from blender_asset_tracer import blendfile
from tests.abstract_test import AbstractBlendFileTest


class ModifyUncompressedTest(AbstractBlendFileTest):
    def setUp(self):
        self.orig = self.blendfiles / "linked_cube.blend"
        self.to_modify = self.orig.with_name("linked_cube_modified.blend")

        copyfile(
            str(self.orig), str(self.to_modify)
        )  # TODO: when requiring Python 3.6+, remove str()
        self.bf = blendfile.BlendFile(self.to_modify, mode="r+b")

        self.assertFalse(self.bf.is_compressed)

    def tearDown(self):
        super().tearDown()
        if self.to_modify.exists():
            self.to_modify.unlink()

    def test_change_path(self):
        library = self.bf.code_index[b"LI"][0]

        # Change it from absolute to relative.
        library[b"filepath"] = b"//basic_file.blend"
        library[b"name"] = b"//basic_file.blend"

        self.reload()

        library = self.bf.code_index[b"LI"][0]
        self.assertEqual(b"//basic_file.blend", library[b"filepath"])
        self.assertEqual(b"//basic_file.blend", library[b"name"])

    def test_block_hash(self):
        scene = self.bf.code_index[b"SC"][0]
        assert isinstance(scene, blendfile.BlendFileBlock)

        pre_hash = scene.hash()
        self.assertIsInstance(pre_hash, int)

        # Change the 'ed' pointer to some arbitrary value by hacking the blend file.
        psize = self.bf.header.pointer_size
        field, field_offset = scene.dna_type.field_from_path(psize, b"ed")
        self.bf.fileobj.seek(scene.file_offset + field_offset, os.SEEK_SET)
        self.bf.fileobj.write(b"12345678"[:psize])

        self.reload()

        scene = self.bf.code_index[b"SC"][0]
        post_hash = scene.hash()
        self.assertEqual(pre_hash, post_hash)

    def reload(self):
        self.bf.close()
        self.bf = blendfile.BlendFile(self.to_modify, mode="r+b")


class ModifyCompressedTest(AbstractBlendFileTest):
    def setUp(self):
        self.orig = self.blendfiles / "linked_cube_compressed.blend"
        self.to_modify = self.orig.with_name("linked_cube_modified.blend")

        copyfile(
            str(self.orig), str(self.to_modify)
        )  # TODO: when requiring Python 3.6+, remove str()
        self.bf = blendfile.BlendFile(self.to_modify, mode="r+b")

        self.assertTrue(self.bf.is_compressed)

    def tearDown(self):
        if self.to_modify.exists():
            self.to_modify.unlink()

    def test_change_path(self):
        library = self.bf.code_index[b"LI"][0]

        # Change it from absolute to relative.
        library[b"filepath"] = b"//basic_file.blend"
        library[b"name"] = b"//basic_file.blend"

        # Reload the blend file to inspect that it was written properly.
        self.bf.close()
        self.bf = blendfile.BlendFile(self.to_modify, mode="r+b")

        library = self.bf.code_index[b"LI"][0]
        self.assertEqual(b"//basic_file.blend", library[b"filepath"])
        self.assertEqual(b"//basic_file.blend", library[b"name"])
