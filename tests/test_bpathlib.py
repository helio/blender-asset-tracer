from pathlib import Path
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
        self.assertTrue(BlendPath(b'C:\\some\\file.blend').is_absolute())
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

    def test_slash(self):
        self.assertEqual(b'/root/and/parent.blend', BlendPath(b'/root/and') / b'parent.blend')
        with self.assertRaises(ValueError):
            BlendPath(b'/root/and') / b'/parent.blend'

        self.assertEqual(b'/root/and/parent.blend', b'/root/and' / BlendPath(b'parent.blend'))
        with self.assertRaises(ValueError):
            b'/root/and' / BlendPath(b'/parent.blend')

    def test_mkrelative(self):
        self.assertEqual(b'//asset.png', BlendPath.mkrelative(
            Path('/path/to/asset.png'),
            Path('/path/to/bfile.blend'),
        ))
        self.assertEqual(b'//to/asset.png', BlendPath.mkrelative(
            Path('/path/to/asset.png'),
            Path('/path/bfile.blend'),
        ))
        self.assertEqual(b'//../of/asset.png', BlendPath.mkrelative(
            Path('/path/of/asset.png'),
            Path('/path/to/bfile.blend'),
        ))
        self.assertEqual(b'//../../path/of/asset.png', BlendPath.mkrelative(
            Path('/path/of/asset.png'),
            Path('/some/weird/bfile.blend'),
        ))
        self.assertEqual(b'//very/very/very/very/very/deep/asset.png', BlendPath.mkrelative(
            Path('/path/to/very/very/very/very/very/deep/asset.png'),
            Path('/path/to/bfile.blend'),
        ))
        self.assertEqual(b'//../../../../../../../../shallow/asset.png', BlendPath.mkrelative(
            Path('/shallow/asset.png'),
            Path('/path/to/very/very/very/very/very/deep/bfile.blend'),
        ))
