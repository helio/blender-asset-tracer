import os

from blender_asset_tracer import blendfile
from blender_asset_tracer.blendfile import iterators
from abstract_test import AbstractBlendFileTest


class BlendFileBlockTest(AbstractBlendFileTest):
    def setUp(self):
        self.bf = blendfile.BlendFile(self.blendfiles / 'basic_file.blend')

    def test_loading(self):
        self.assertFalse(self.bf.is_compressed)

    def test_some_properties(self):
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
             ],
            list(gen)[:6])

    def test_iter_recursive(self):
        ob = self.bf.code_index[b'OB'][0]
        assert isinstance(ob, blendfile.BlendFileBlock)

        # We can't test all of them in a reliable way, but it shouldn't crash.
        all_items = list(ob.items_recursive())

        # And we can check the first few items.
        self.assertEqual(
            [((b'id', b'next'), 0),
             ((b'id', b'prev'), 0),
             ((b'id', b'newid'), 0),
             ((b'id', b'lib'), 0),
             ((b'id', b'name'),
              b'OB\xc3\xbcmlaut'),
             ((b'id', b'flag'), 0),
             ], all_items[:6])

    def test_items(self):
        ma = self.bf.code_index[b'MA'][0]
        assert isinstance(ma, blendfile.BlendFileBlock)

        # We can't test all of them in a reliable way, but it shouldn't crash.
        all_items = list(ma.items())

        # And we can check the first few items.
        self.assertEqual(
            [(b'id', '<ID>'),  # not recursed into.
             (b'adt', 0),
             (b'material_type', 0),
             (b'flag', 0),
             (b'r', 0.8000000715255737),
             (b'g', 0.03218378871679306),
             (b'b', 0.36836329102516174),
             (b'specr', 1.0)],
            all_items[:8])

    def test_keys(self):
        ma = self.bf.code_index[b'MA'][0]
        assert isinstance(ma, blendfile.BlendFileBlock)

        # We can't test all of them in a reliable way, but it shouldn't crash.
        all_keys = list(ma.keys())

        # And we can check the first few items.
        self.assertEqual(
            [b'id', b'adt', b'material_type', b'flag', b'r', b'g', b'b', b'specr'],
            all_keys[:8])

    def test_values(self):
        ma = self.bf.code_index[b'MA'][0]
        assert isinstance(ma, blendfile.BlendFileBlock)

        # We can't test all of them in a reliable way, but it shouldn't crash.
        all_values = list(ma.values())

        # And we can check the first few items.
        self.assertEqual(
            ['<ID>',
             0,
             0,
             0,
             0.8000000715255737,
             0.03218378871679306,
             0.36836329102516174,
             1.0],
            all_values[:8])

    def test_get_via_dict_interface(self):
        ma = self.bf.code_index[b'MA'][0]
        assert isinstance(ma, blendfile.BlendFileBlock)
        self.assertEqual(0.8000000715255737, ma[b'r'])

        ob = self.bf.code_index[b'OB'][0]
        assert isinstance(ob, blendfile.BlendFileBlock)
        self.assertEqual('OBümlaut', ob[b'id', b'name'].decode())


class PointerTest(AbstractBlendFileTest):
    def setUp(self):
        self.bf = blendfile.BlendFile(self.blendfiles / 'with_sequencer.blend')

    def test_get_pointer_and_listbase(self):
        scenes = self.bf.code_index[b'SC']
        self.assertEqual(1, len(scenes), 'expecting 1 scene')
        scene = scenes[0]
        self.assertEqual(b'SCScene', scene[b'id', b'name'])

        ed_ptr = scene[b'ed']
        self.assertEqual(140051431100936, ed_ptr)

        ed = scene.get_pointer(b'ed')
        self.assertEqual(140051431100936, ed.addr_old)

        seqbase = ed.get_pointer((b'seqbase', b'first'))
        self.assertIsNotNone(seqbase)

        types = {
            b'SQBlack': 28,
            b'SQCross': 8,
            b'SQPink': 28,
        }
        seq = None
        for seq in iterators.listbase(seqbase):
            seq.refine_type(b'Sequence')
            name = seq[b'name']
            expected_type = types[name]
            self.assertEqual(expected_type, seq[b'type'])

        # The last 'seq' from the loop should be the last in the list.
        seq_next = seq.get_pointer(b'next')
        self.assertIsNone(seq_next)

    def test_refine_sdna_by_name(self):
        scene = self.bf.code_index[b'SC'][0]
        ed = scene.get_pointer(b'ed')

        seq = ed.get_pointer((b'seqbase', b'first'))

        # This is very clear to me:
        seq.refine_type(b'Sequence')
        self.assertEqual(b'SQBlack', seq[b'name'])
        self.assertEqual(28, seq[b'type'])

    def test_refine_sdna_by_idx(self):
        scene = self.bf.code_index[b'SC'][0]
        ed = scene.get_pointer(b'ed')
        seq = ed.get_pointer((b'seqbase', b'first'))

        sdna_idx_sequence = self.bf.sdna_index_from_id[b'Sequence']
        seq.refine_type_from_index(sdna_idx_sequence)
        self.assertEqual(b'SQBlack', seq[b'name'])
        self.assertEqual(28, seq[b'type'])


class LoadCompressedTest(AbstractBlendFileTest):
    def test_loading(self):
        self.bf = blendfile.BlendFile(self.blendfiles / 'basic_file_compressed.blend')
        self.assertTrue(self.bf.is_compressed)

        ob = self.bf.code_index[b'OB'][0]
        name = ob.get((b'id', b'name'))
        self.assertEqual('OBümlaut', name)
