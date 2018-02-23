from shutil import copyfile

from blender_asset_tracer import blendfile
from abstract_test import AbstractBlendFileTest


class ModifyUncompressedTest(AbstractBlendFileTest):
    def setUp(self):
        self.orig = self.blendfiles / 'linked_cube.blend'
        self.to_modify = self.orig.with_name('linked_cube_modified.blend')

        copyfile(str(self.orig), str(self.to_modify))  # TODO: when requiring Python 3.6+, remove str()
        self.bf = blendfile.BlendFile(self.to_modify, mode='r+b')

        self.assertFalse(self.bf.is_compressed)

    def tearDown(self):
        if self.to_modify.exists():
            self.to_modify.unlink()

    def test_change_path(self):
        library = self.bf.code_index[b'LI'][0]

        # Change it from absolute to relative.
        library[b'filepath'] = b'//basic_file.blend'
        library[b'name'] = b'//basic_file.blend'

        # Reload the blend file to inspect that it was written properly.
        self.bf.close()
        self.bf = blendfile.BlendFile(self.to_modify, mode='r+b')

        library = self.bf.code_index[b'LI'][0]
        self.assertEqual(b'//basic_file.blend', library[b'filepath'])
        self.assertEqual(b'//basic_file.blend', library[b'name'])
