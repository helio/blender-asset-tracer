from pathlib import Path, PurePosixPath
import unittest
from unittest import mock

from blender_asset_tracer.bpathlib import BlendPath


class BlendPathTest(unittest.TestCase):
    def test_string_path(self):
        p = BlendPath(PurePosixPath('//some/file.blend'))
        self.assertEqual('//some/file.blend', str(PurePosixPath('//some/file.blend')))
        self.assertEqual(b'//some/file.blend', p)

        p = BlendPath(Path(r'C:\some\file.blend'))
        self.assertEqual(b'C:/some/file.blend', p)

    def test_invalid_type(self):
        with self.assertRaises(TypeError):
            BlendPath('//some/file.blend')
        with self.assertRaises(TypeError):
            BlendPath(47)
        with self.assertRaises(TypeError):
            BlendPath(None)

    def test_repr(self):
        p = BlendPath(b'//some/file.blend')
        self.assertEqual("BlendPath(b'//some/file.blend')", repr(p))
        p = BlendPath(PurePosixPath('//some/file.blend'))
        self.assertEqual("BlendPath(b'//some/file.blend')", repr(p))

    def test_to_path(self):
        self.assertEqual(PurePosixPath('/some/file.blend'),
                         BlendPath(b'/some/file.blend').to_path())
        self.assertEqual(PurePosixPath('C:/some/file.blend'),
                         BlendPath(b'C:/some/file.blend').to_path())
        self.assertEqual(PurePosixPath('C:/some/file.blend'),
                         BlendPath(br'C:\some\file.blend').to_path())

        with mock.patch('sys.getfilesystemencoding') as mock_getfse:
            mock_getfse.return_value = 'latin1'

            # \xe9 is Latin-1 for é, and BlendPath should revert to using the
            # (mocked) filesystem encoding when decoding as UTF-8 fails.
            self.assertEqual(PurePosixPath('C:/some/filé.blend'),
                             BlendPath(b'C:\\some\\fil\xe9.blend').to_path())

        with self.assertRaises(ValueError):
            BlendPath(b'//relative/path.jpg').to_path()

    def test_is_absolute(self):
        self.assertFalse(BlendPath(b'//some/file.blend').is_absolute())
        self.assertTrue(BlendPath(b'/some/file.blend').is_absolute())
        self.assertTrue(BlendPath(b'C:/some/file.blend').is_absolute())
        self.assertTrue(BlendPath(b'C:\\some\\file.blend').is_absolute())
        self.assertFalse(BlendPath(b'some/file.blend').is_absolute())

    def test_is_blendfile_relative(self):
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

        # On Windows+Python 3.5.4 this resulted in b'//root//parent.blend',
        # but only if the root is a single term (so not b'//root/and/').
        self.assertEqual(BlendPath(b'//root/parent.blend'),
                         BlendPath(b'//root/') / b'parent.blend')

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
