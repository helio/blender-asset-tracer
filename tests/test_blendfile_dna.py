import io
import os
import unittest
from unittest import mock

from blender_asset_tracer.blendfile import dna, dna_io


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
    class FakeHeader:
        pointer_size = 8
        endian = dna_io.BigEndianTypes

    def setUp(self):
        self.s = dna.Struct(b'AlembicObjectPath')
        self.s_char = dna.Struct(b'char', 1)
        self.s_float = dna.Struct(b'float', 4)
        self.s_uint64 = dna.Struct(b'uint64_t', 8)
        self.s_uint128 = dna.Struct(b'uint128_t', 16)  # non-supported type

        self.f_next = dna.Field(self.s, dna.Name(b'*next'), 8, 0)
        self.f_prev = dna.Field(self.s, dna.Name(b'*prev'), 8, 8)
        self.f_path = dna.Field(self.s_char, dna.Name(b'path[4096]'), 4096, 16)
        self.f_pointer = dna.Field(self.s_char, dna.Name(b'*ptr'), 3 * 8, 4112)
        self.f_number = dna.Field(self.s_uint64, dna.Name(b'numbah'), 8, 4136)
        self.f_floaty = dna.Field(self.s_float, dna.Name(b'floaty[2]'), 2 * 4, 4144)
        self.f_flag = dna.Field(self.s_char, dna.Name(b'bitflag'), 1, 4152)
        self.f_bignum = dna.Field(self.s_uint128, dna.Name(b'bignum'), 16, 4153)

        self.s.append_field(self.f_next)
        self.s.append_field(self.f_prev)
        self.s.append_field(self.f_path)
        self.s.append_field(self.f_pointer)
        self.s.append_field(self.f_number)
        self.s.append_field(self.f_floaty)
        self.s.append_field(self.f_flag)
        self.s.append_field(self.f_bignum)

    def test_autosize(self):
        with self.assertRaises(ValueError):
            # Maybe it would be better to just return 0 on empty structs.
            # They are actually used in Blendfiles (for example
            # AbcArchiveHandle), but when actually loading from a blendfile
            # the size property is explicitly set anyway. The situation we
            # test here is for manually created Struct instances that don't
            # have any fields.
            dna.Struct(b'EmptyStruct').size

        # Create AlebicObjectPath as it is actually used in Blender 2.79a
        s = dna.Struct(b'AlembicObjectPath')
        f_next = dna.Field(s, dna.Name(b'*next'), 8, 0)
        f_prev = dna.Field(s, dna.Name(b'*prev'), 8, 8)
        f_path = dna.Field(self.s_char, dna.Name(b'path[4096]'), 4096, 16)
        s.append_field(f_next)
        s.append_field(f_prev)
        s.append_field(f_path)

        self.assertEqual(s.size, 4112)

    def test_field_from_path(self):
        psize = 8
        self.assertEqual(self.s.field_from_path(psize, b'path'),
                         (self.f_path, 16))
        self.assertEqual(self.s.field_from_path(psize, (b'prev', b'path')),
                         (self.f_path, 24))
        self.assertEqual(self.s.field_from_path(psize, (b'ptr', 2)),
                         (self.f_pointer, 16 + 4096 + 2 * psize))
        self.assertEqual(self.s.field_from_path(psize, (b'floaty', 1)),
                         (self.f_floaty, 4144 + self.s_float.size))

        with self.assertRaises(OverflowError):
            self.s.field_from_path(psize, (b'floaty', 2))

        with self.assertRaises(KeyError):
            self.s.field_from_path(psize, b'non-existant')

        with self.assertRaises(TypeError):
            self.s.field_from_path(psize, 'path')

    def test_simple_field_get(self):
        fileobj = mock.MagicMock(io.BufferedReader)
        fileobj.read.return_value = b'\x01\x02\x03\x04\xff\xfe\xfd\xfa'
        val = self.s.field_get(self.FakeHeader(), fileobj, b'numbah')

        self.assertEqual(val, 0x1020304fffefdfa)
        fileobj.seek.assert_called_with(4136, os.SEEK_CUR)

    def test_field_get_default(self):
        fileobj = mock.MagicMock(io.BufferedReader)
        fileobj.read.side_effect = RuntimeError
        val = self.s.field_get(self.FakeHeader(), fileobj, b'nonexistant', default=519871531)

        self.assertEqual(val, 519871531)
        fileobj.seek.assert_not_called()

    def test_field_get_nonexistant(self):
        fileobj = mock.MagicMock(io.BufferedReader)
        fileobj.read.side_effect = RuntimeError

        with self.assertRaises(KeyError):
            self.s.field_get(self.FakeHeader(), fileobj, b'nonexistant')
        fileobj.seek.assert_not_called()

    def test_field_get_unsupported_type(self):
        fileobj = mock.MagicMock(io.BufferedReader)
        fileobj.read.side_effect = RuntimeError

        with self.assertRaises(NotImplementedError):
            self.s.field_get(self.FakeHeader(), fileobj, b'bignum')
        fileobj.seek.assert_called_with(4153, os.SEEK_CUR)

    def test_pointer_field_get(self):
        fileobj = mock.MagicMock(io.BufferedReader)
        fileobj.read.return_value = b'\xf0\x9f\xa6\x87\x00dum'
        val = self.s.field_get(self.FakeHeader(), fileobj, b'ptr')

        self.assertEqual(0xf09fa6870064756d, val)
        fileobj.seek.assert_called_with(4112, os.SEEK_CUR)

    def test_string_field_get(self):
        fileobj = mock.MagicMock(io.BufferedReader)
        fileobj.read.return_value = b'\xf0\x9f\xa6\x87\x00dummydata'
        val = self.s.field_get(self.FakeHeader(), fileobj, b'path', as_str=True)

        self.assertEqual('🦇', val)
        fileobj.seek.assert_called_with(16, os.SEEK_CUR)

    def test_string_field_get_single_char(self):
        fileobj = mock.MagicMock(io.BufferedReader)
        fileobj.read.return_value = b'\xf0'
        val = self.s.field_get(self.FakeHeader(), fileobj, b'bitflag')

        self.assertEqual(0xf0, val)
        fileobj.seek.assert_called_with(4152, os.SEEK_CUR)

    def test_string_field_get_invalid_utf8(self):
        fileobj = mock.MagicMock(io.BufferedReader)
        fileobj.read.return_value = b'\x01\x02\x03\x04\xff\xfe\xfd\xfa'

        with self.assertRaises(UnicodeDecodeError):
            self.s.field_get(self.FakeHeader(), fileobj, b'path', as_str=True)

    def test_string_field_get_bytes_null_terminated(self):
        fileobj = mock.MagicMock(io.BufferedReader)
        fileobj.read.return_value = b'\x01\x02\x03\x04\xff\xfe\xfd\xfa\x00dummydata'

        val = self.s.field_get(self.FakeHeader(), fileobj, b'path', as_str=False)
        self.assertEqual(b'\x01\x02\x03\x04\xff\xfe\xfd\xfa', val)
        fileobj.seek.assert_called_with(16, os.SEEK_CUR)

    def test_string_field_get_bytes(self):
        fileobj = mock.MagicMock(io.BufferedReader)
        fileobj.read.return_value = b'\x01\x02\x03\x04\xff\xfe\xfd\xfa\x00dummydata'

        val = self.s.field_get(self.FakeHeader(), fileobj, b'path',
                               as_str=False, null_terminated=False)
        self.assertEqual(b'\x01\x02\x03\x04\xff\xfe\xfd\xfa\x00dummydata', val)
        fileobj.seek.assert_called_with(16, os.SEEK_CUR)

    def test_string_field_get_float_array(self):
        fileobj = mock.MagicMock(io.BufferedReader)
        fileobj.read.side_effect = (b'@333', b'@2\x8f\\')

        val = self.s.field_get(self.FakeHeader(), fileobj, b'floaty')
        self.assertAlmostEqual(2.8, val[0])
        self.assertAlmostEqual(2.79, val[1])
        fileobj.seek.assert_called_with(4144, os.SEEK_CUR)
