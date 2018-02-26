import unittest

from blender_asset_tracer.bpathlib import BlendPath


class BlendPathTest(unittest.TestCase):
    def test_string_path(self):
        p = BlendPath('//some/file.blend')
        self.assertEqual(b'//some/file.blend', p)

        p = BlendPath(r'C:\some\file.blend')
        self.assertEqual(b'C:\\some\\file.blend', p)

    def test_is_absolute(self):
        self.assertFalse(BlendPath('//some/file.blend').is_absolute())
        self.assertTrue(BlendPath('/some/file.blend').is_absolute())
        self.assertTrue(BlendPath('C:/some/file.blend').is_absolute())
        self.assertFalse(BlendPath('some/file.blend').is_absolute())

        self.assertFalse(BlendPath(b'//some/file.blend').is_absolute())
        self.assertTrue(BlendPath(b'/some/file.blend').is_absolute())
        self.assertTrue(BlendPath(b'C:/some/file.blend').is_absolute())
        self.assertFalse(BlendPath(b'some/file.blend').is_absolute())

    def test_is_blendfile_relative(self):
        self.assertTrue(BlendPath('//some/file.blend').is_blendfile_relative())
        self.assertFalse(BlendPath('/some/file.blend').is_blendfile_relative())
        self.assertFalse(BlendPath('C:/some/file.blend').is_blendfile_relative())
        self.assertFalse(BlendPath('some/file.blend').is_blendfile_relative())

        self.assertTrue(BlendPath(b'//some/file.blend').is_blendfile_relative())
        self.assertFalse(BlendPath(b'/some/file.blend').is_blendfile_relative())
        self.assertFalse(BlendPath(b'C:/some/file.blend').is_blendfile_relative())
        self.assertFalse(BlendPath(b'some/file.blend').is_blendfile_relative())

    def test_make_absolute(self):
        self.assertEqual(b'/root/to/some/file.blend',
                         BlendPath(b'//some/file.blend').absolute(b'/root/to'))
        self.assertEqual(b'/root/to/some/file.blend',
                         BlendPath(b'some/file.blend').absolute(b'/root/to'))
        self.assertEqual(b'/root/to/../some/file.blend',
                         BlendPath(b'../some/file.blend').absolute(b'/root/to'))
        self.assertEqual(b'/shared/some/file.blend',
                         BlendPath(b'/shared/some/file.blend').absolute(b'/root/to'))
