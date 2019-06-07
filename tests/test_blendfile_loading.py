import os
import pathlib
import tempfile

from blender_asset_tracer import blendfile
from blender_asset_tracer.blendfile import iterators, exceptions
from tests.abstract_test import AbstractBlendFileTest


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
        _, loc = ob.dna_type.field_get(self.bf.header, self.bf.fileobj, b'loc')
        self.assertEqual([2.0, 3.0, 5.0], loc)

        # Try low level operation to read an array element.
        self.bf.fileobj.seek(ob.file_offset, os.SEEK_SET)
        _, loc_z = ob.dna_type.field_get(self.bf.header, self.bf.fileobj, (b'loc', 2))
        self.assertEqual(5.0, loc_z)

        # Try high level operation to read the same property.
        loc = ob.get(b'loc')
        self.assertEqual([2.0, 3.0, 5.0], loc)

        # Try getting a subproperty.
        name = ob.get((b'id', b'name'), as_str=True)
        self.assertEqual('OBümlaut', name)

        loc_z = ob.get((b'loc', 2))
        self.assertEqual(5.0, loc_z)

        # Try following a pointer.
        mesh_ptr = ob.get(b'data')
        mesh = self.bf.block_from_addr[mesh_ptr]
        mname = mesh.get((b'id', b'name'), as_str=True)
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
        self.assertAlmostEqual(0.8000000715255737, ma[b'r'])

        ob = self.bf.code_index[b'OB'][0]
        assert isinstance(ob, blendfile.BlendFileBlock)
        self.assertEqual('OBümlaut', ob.id_name.decode())


class PointerTest(AbstractBlendFileTest):
    def setUp(self):
        self.bf = blendfile.BlendFile(self.blendfiles / 'with_sequencer.blend')

    def test_get_pointer_and_listbase(self):
        scenes = self.bf.code_index[b'SC']
        self.assertEqual(1, len(scenes), 'expecting 1 scene')
        scene = scenes[0]
        self.assertEqual(b'SCScene', scene.id_name)

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

    def test_segfault(self):
        scene = self.bf.code_index[b'SC'][0]
        ed_ptr = scene.get(b'ed')
        del self.bf.block_from_addr[ed_ptr]

        with self.assertRaises(exceptions.SegmentationFault):
            scene.get_pointer(b'ed')

    def test_abs_offset(self):
        scene = self.bf.code_index[b'SC'][0]
        ed = scene.get_pointer(b'ed')
        assert isinstance(ed, blendfile.BlendFileBlock)

        abs_offset, field_size = ed.abs_offset((b'seqbase', b'first'))
        self.assertEqual(ed.file_offset + 8, abs_offset)
        self.assertEqual(1, field_size)


class ArrayTest(AbstractBlendFileTest):
    def test_array_of_pointers(self):
        self.bf = blendfile.BlendFile(self.blendfiles / 'multiple_materials.blend')
        mesh = self.bf.code_index[b'ME'][0]
        assert isinstance(mesh, blendfile.BlendFileBlock)

        material_count = mesh[b'totcol']
        self.assertEqual(4, material_count)

        for i, material in enumerate(mesh.iter_array_of_pointers(b'mat', material_count)):
            if i == 0:
                name = b'MAMaterial.000'
            elif i in {1, 3}:
                name = b'MAMaterial.001'
            else:
                name = b'MAMaterial.002'
            self.assertEqual(name, material.id_name)

    def test_array_of_lamp_textures(self):
        self.bf = blendfile.BlendFile(self.blendfiles / 'lamp_textures.blend')
        lamp = self.bf.code_index[b'LA'][0]
        assert isinstance(lamp, blendfile.BlendFileBlock)

        mtex0 = lamp.get_pointer(b'mtex')
        tex = mtex0.get_pointer(b'tex')
        self.assertEqual(b'TE', tex.code)
        self.assertEqual(b'TEClouds', tex.id_name)

        for i, mtex in enumerate(lamp.iter_fixed_array_of_pointers(b'mtex')):
            if i == 0:
                name = b'TEClouds'
            elif i == 1:
                name = b'TEVoronoi'
            else:
                self.fail('Too many textures reported: %r' % mtex)

            tex = mtex.get_pointer(b'tex')
            self.assertEqual(b'TE', tex.code)
            self.assertEqual(name, tex.id_name)


class LoadCompressedTest(AbstractBlendFileTest):
    def test_loading(self):
        self.bf = blendfile.BlendFile(self.blendfiles / 'basic_file_compressed.blend')
        self.assertTrue(self.bf.is_compressed)

        ob = self.bf.code_index[b'OB'][0]
        name = ob.get((b'id', b'name'), as_str=True)
        self.assertEqual('OBümlaut', name)

    def test_as_context(self):
        with blendfile.BlendFile(self.blendfiles / 'basic_file_compressed.blend') as bf:
            filepath = bf.filepath
            raw_filepath = bf.raw_filepath

        self.assertTrue(bf.fileobj.closed)
        self.assertTrue(filepath.exists())
        self.assertFalse(raw_filepath.exists())


class LoadNonBlendfileTest(AbstractBlendFileTest):
    def test_loading(self):
        with self.assertRaises(exceptions.BlendFileError):
            blendfile.BlendFile(pathlib.Path(__file__))

    def test_no_datablocks(self):
        with self.assertRaises(exceptions.NoDNA1Block):
            blendfile.BlendFile(self.blendfiles / 'corrupt_only_magic.blend')


class BlendFileCacheTest(AbstractBlendFileTest):
    def setUp(self):
        super().setUp()
        self.tdir = tempfile.TemporaryDirectory()
        self.tpath = pathlib.Path(self.tdir.name)

    def tearDown(self):
        super().tearDown()
        self.tdir.cleanup()

    def test_open_cached(self):
        infile = self.blendfiles / 'basic_file.blend'
        bf1 = blendfile.open_cached(infile)
        bf2 = blendfile.open_cached(infile)

        # The file should only be opened & parsed once.
        self.assertIs(bf1, bf2)
        self.assertIs(bf1, blendfile._cached_bfiles[infile])

    def test_compressed(self):
        infile = self.blendfiles / 'linked_cube_compressed.blend'
        bf1 = blendfile.open_cached(infile)
        bf2 = blendfile.open_cached(infile)

        # The file should only be opened & parsed once.
        self.assertIs(bf1, bf2)
        self.assertIs(bf1, blendfile._cached_bfiles[infile])

    def test_closed(self):
        infile = self.blendfiles / 'linked_cube_compressed.blend'
        bf = blendfile.open_cached(infile)
        self.assertIs(bf, blendfile._cached_bfiles[infile])

        blendfile.close_all_cached()
        self.assertTrue(bf.fileobj.closed)
        self.assertEqual({}, blendfile._cached_bfiles)

    def test_close_one_file(self):
        path1 = self.blendfiles / 'linked_cube_compressed.blend'
        path2 = self.blendfiles / 'basic_file.blend'
        bf1 = blendfile.open_cached(path1)
        bf2 = blendfile.open_cached(path2)
        self.assertIs(bf1, blendfile._cached_bfiles[path1])

        # Closing a file should remove it from the cache.
        bf1.close()
        self.assertTrue(bf1.fileobj.closed)
        self.assertEqual({path2: bf2}, blendfile._cached_bfiles)

    def test_open_and_rebind(self):
        infile = self.blendfiles / 'linked_cube.blend'
        other = self.tpath / 'copy.blend'
        self._open_and_rebind_test(infile, other)

    def test_open_and_rebind_compressed(self):
        infile = self.blendfiles / 'linked_cube_compressed.blend'
        other = self.tpath / 'copy.blend'
        self._open_and_rebind_test(infile, other)

    def _open_and_rebind_test(self, infile: pathlib.Path, other: pathlib.Path):
        self.assertFalse(other.exists())

        bf = blendfile.open_cached(infile)

        self.assertEqual(str(bf.raw_filepath), bf.fileobj.name)

        before_filepath = bf.filepath
        before_raw_fp = bf.raw_filepath
        before_blocks = bf.blocks
        before_compressed = bf.is_compressed

        bf.copy_and_rebind(other, mode='rb+')

        self.assertTrue(other.exists())
        self.assertEqual(before_compressed, bf.is_compressed)

        if bf.is_compressed:
            self.assertNotEqual(bf.filepath, bf.raw_filepath)
        else:
            self.assertEqual(bf.filepath, bf.raw_filepath)

        self.assertNotEqual(before_filepath, bf.filepath)
        self.assertNotEqual(before_raw_fp, bf.raw_filepath)
        self.assertEqual(other, bf.filepath)
        self.assertIs(before_blocks, bf.blocks)
        self.assertNotIn(infile, blendfile._cached_bfiles)
        self.assertIs(bf, blendfile._cached_bfiles[other])

        self.assertEqual(str(bf.raw_filepath), bf.fileobj.name)
