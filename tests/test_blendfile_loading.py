import pathlib
import unittest

import os

from blender_asset_tracer import blendfile


class BlendLoadingTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.blendfiles = pathlib.Path(__file__).with_name('blendfiles')

    def setUp(self):
        self.bf = None

    def tearDown(self):
        if self.bf:
            self.bf.close()

    def test_some_properties(self):
        self.bf = blendfile.BlendFile(self.blendfiles / 'basic_file.blend')
        self.assertFalse(self.bf.is_compressed)
        self.assertEqual(1, len(self.bf.code_index[b'OB']))
        ob = self.bf.code_index[b'OB'][0]
        self.assertEqual('Object', ob.dna_type_name)

        # Try low level operation to read a property.
        self.bf.fileobj.seek(ob.file_offset, os.SEEK_SET)
        loc = ob.dna_type.field_get(self.bf.header, self.bf.fileobj, b'loc')
        self.assertEqual(loc, [2.0, 3.0, 5.0])

        # Try high level operation to read the same property.
        loc = ob.get(b'loc')
        self.assertEqual(loc, [2.0, 3.0, 5.0])

        # Try getting a subproperty.
        name = ob.get((b'id', b'name'))
        self.assertEqual('OBümlaut', name)

        # Try following a pointer.
        mesh_ptr = ob.get(b'data')
        mesh = self.bf.block_from_offset[mesh_ptr]
        mname = mesh.get((b'id', b'name'))
        self.assertEqual('MECube³', mname)
