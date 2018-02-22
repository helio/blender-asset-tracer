import unittest

from blender_asset_tracer.blendfile import dna


class NameTest(unittest.TestCase):
    def test_simple_name(self):
        n = dna.Name(b'Suzanne')
        self.assertEqual(n.name_full, b'Suzanne')
        self.assertEqual(n.name_only, b'Suzanne')
        self.assertFalse(n.is_pointer)
        self.assertFalse(n.is_method_pointer)
        self.assertEqual(n.array_size, 1)

    def test_pointer(self):
        n = dna.Name(b'*marker')
        self.assertEqual(n.name_full, b'*marker')
        self.assertEqual(n.name_only, b'marker')
        self.assertTrue(n.is_pointer)
        self.assertFalse(n.is_method_pointer)
        self.assertEqual(n.array_size, 1)

    def test_method_pointer(self):
        n = dna.Name(b'(*delta_cache)()')
        self.assertEqual(n.name_full, b'(*delta_cache)()')
        self.assertEqual(n.name_only, b'delta_cache')
        self.assertTrue(n.is_pointer)
        self.assertTrue(n.is_method_pointer)
        self.assertEqual(n.array_size, 1)

    def test_simple_array(self):
        n = dna.Name(b'flame_smoke_color[3]')
        self.assertEqual(n.name_full, b'flame_smoke_color[3]')
        self.assertEqual(n.name_only, b'flame_smoke_color')
        self.assertFalse(n.is_pointer)
        self.assertFalse(n.is_method_pointer)
        self.assertEqual(n.array_size, 3)

    def test_nested_array(self):
        n = dna.Name(b'pattern_corners[4][2]')
        self.assertEqual(n.name_full, b'pattern_corners[4][2]')
        self.assertEqual(n.name_only, b'pattern_corners')
        self.assertFalse(n.is_pointer)
        self.assertFalse(n.is_method_pointer)
        self.assertEqual(n.array_size, 8)

    def test_pointer_array(self):
        n = dna.Name(b'*mtex[18]')
        self.assertEqual(n.name_full, b'*mtex[18]')
        self.assertEqual(n.name_only, b'mtex')
        self.assertTrue(n.is_pointer)
        self.assertFalse(n.is_method_pointer)
        self.assertEqual(n.array_size, 18)

    def test_repr(self):
        self.assertEqual(repr(dna.Name(b'Suzanne')), "Name(b'Suzanne')")
        self.assertEqual(repr(dna.Name(b'*marker')), "Name(b'*marker')")
        self.assertEqual(repr(dna.Name(b'(*delta_cache)()')), "Name(b'(*delta_cache)()')")
        self.assertEqual(repr(dna.Name(b'flame_smoke_color[3]')), "Name(b'flame_smoke_color[3]')")
        self.assertEqual(repr(dna.Name(b'pattern_corners[4][2]')), "Name(b'pattern_corners[4][2]')")
        self.assertEqual(repr(dna.Name(b'*mtex[18]')), "Name(b'*mtex[18]')")

    def test_as_reference(self):
        n = dna.Name(b'(*delta_cache)()')
        self.assertEqual(n.as_reference(None), b'delta_cache')
        self.assertEqual(n.as_reference(b''), b'delta_cache')
        self.assertEqual(n.as_reference(b'parent'), b'parent.delta_cache')


class StructTest(unittest.TestCase):
    def test_field_from_path(self):
        s = dna.Struct(b'AlembicObjectPath')
        f_next = dna.Field(s, dna.Name(b'*next'), 8, 0)
        f_prev = dna.Field(s, dna.Name(b'*prev'), 8, 8)
        f_path = dna.Field(dna.Struct(b'char'), dna.Name(b'path[4096]'), 4096, 16)
        f_pointer = dna.Field(dna.Struct(b'char'), dna.Name(b'*ptr'), 3 * 8, 16 + 4096)
        s.append_field(f_next)
        s.append_field(f_prev)
        s.append_field(f_path)
        s.append_field(f_pointer)

        psize = 8
        self.assertEqual(s.field_from_path(psize, b'path'), (f_path, 16))
        self.assertEqual(s.field_from_path(psize, (b'prev', b'path')), (f_path, 16))
        self.assertEqual(s.field_from_path(psize, (b'ptr', 2)), (f_pointer, 16 + 4096 + 2 * psize))
