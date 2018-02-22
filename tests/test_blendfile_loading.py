import pathlib
import unittest

import os

from blender_asset_tracer import blendfile


class BlendFileBlockTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.blendfiles = pathlib.Path(__file__).with_name('blendfiles')

    def setUp(self):
        self.bf = None

    def tearDown(self):
        if self.bf:
            self.bf.close()

    def test_loading(self):
        self.bf = blendfile.BlendFile(self.blendfiles / 'basic_file.blend')
        self.assertFalse(self.bf.is_compressed)

    def test_some_properties(self):
        self.bf = blendfile.BlendFile(self.blendfiles / 'basic_file.blend')
        ob = self.bf.code_index[b'OB'][0]
        self.assertEqual('Object', ob.dna_type_name)

        # Try low level operation to read a property.
        self.bf.fileobj.seek(ob.file_offset, os.SEEK_SET)
        loc = ob.dna_type.field_get(self.bf.header, self.bf.fileobj, b'loc')
        self.assertEqual([2.0, 3.0, 5.0], loc)

        # Try low level operation to read an array element.
        self.bf.fileobj.seek(ob.file_offset, os.SEEK_SET)
        loc_z = ob.dna_type.field_get(self.bf.header, self.bf.fileobj, (b'loc', 2))
        self.assertEqual(5.0, loc_z)

        # Try high level operation to read the same property.
        loc = ob.get(b'loc')
        self.assertEqual([2.0, 3.0, 5.0], loc)

        # Try getting a subproperty.
        name = ob.get((b'id', b'name'))
        self.assertEqual('OBümlaut', name)

        loc_z = ob.get((b'loc', 2))
        self.assertEqual(5.0, loc_z)

        # Try following a pointer.
        mesh_ptr = ob.get(b'data')
        mesh = self.bf.block_from_addr[mesh_ptr]
        mname = mesh.get((b'id', b'name'))
        self.assertEqual('MECube³', mname)

    def test_get_recursive_iter(self):
        self.bf = blendfile.BlendFile(self.blendfiles / 'basic_file.blend')
        ob = self.bf.code_index[b'OB'][0]
        assert isinstance(ob, blendfile.BlendFileBlock)

        # No recursing, just an array property.
        gen = ob.get_recursive_iter(b'loc')
        self.assertEqual([(b'loc', [2.0, 3.0, 5.0])], list(gen))

        # Recurse into an object
        gen = ob.get_recursive_iter(b'id')
        self.assertEqual(
            [((b'id', b'next'), 0),
             ((b'id', b'prev'), 0),
             ((b'id', b'newid'), 0),
             ((b'id', b'lib'), 0),
             ((b'id', b'name'), 'OBümlaut'),
             ((b'id', b'flag'), 0),
             ((b'id', b'tag'), 1024),
             ((b'id', b'us'), 1),
             ((b'id', b'icon_id'), 0),
             ((b'id', b'recalc'), 0),
             ((b'id', b'pad'), 0),
             ],
            list(gen)[:-2])  # the last 2 properties are pointers and change when saving.
