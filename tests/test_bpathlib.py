import os
from pathlib import Path, PurePath, PurePosixPath, PureWindowsPath
import platform
import tempfile
import unittest
from unittest import mock

from blender_asset_tracer.bpathlib import BlendPath, make_absolute, strip_root


class BlendPathTest(unittest.TestCase):
    def test_string_path(self):
        p = BlendPath(PurePosixPath("//some/file.blend"))
        self.assertEqual("//some/file.blend", str(PurePosixPath("//some/file.blend")))
        self.assertEqual(b"//some/file.blend", p)

        p = BlendPath(Path(r"C:\some\file.blend"))
        self.assertEqual(b"C:/some/file.blend", p)

    def test_invalid_type(self):
        with self.assertRaises(TypeError):
            BlendPath("//some/file.blend")
        with self.assertRaises(TypeError):
            BlendPath(47)
        with self.assertRaises(TypeError):
            BlendPath(None)

    def test_repr(self):
        p = BlendPath(b"//some/file.blend")
        self.assertEqual("BlendPath(b'//some/file.blend')", repr(p))
        p = BlendPath(PurePosixPath("//some/file.blend"))
        self.assertEqual("BlendPath(b'//some/file.blend')", repr(p))

    def test_to_path(self):
        self.assertEqual(
            PurePath("/some/file.blend"), BlendPath(b"/some/file.blend").to_path()
        )
        self.assertEqual(
            PurePath("C:/some/file.blend"), BlendPath(b"C:/some/file.blend").to_path()
        )
        self.assertEqual(
            PurePath("C:/some/file.blend"), BlendPath(br"C:\some\file.blend").to_path()
        )

        with mock.patch("sys.getfilesystemencoding") as mock_getfse:
            mock_getfse.return_value = "latin1"

            # \xe9 is Latin-1 for é, and BlendPath should revert to using the
            # (mocked) filesystem encoding when decoding as UTF-8 fails.
            self.assertEqual(
                PurePath("C:/some/filé.blend"),
                BlendPath(b"C:\\some\\fil\xe9.blend").to_path(),
            )

        with self.assertRaises(ValueError):
            BlendPath(b"//relative/path.jpg").to_path()

    def test_is_absolute(self):
        self.assertFalse(BlendPath(b"//some/file.blend").is_absolute())
        self.assertTrue(BlendPath(b"/some/file.blend").is_absolute())
        self.assertTrue(BlendPath(b"C:/some/file.blend").is_absolute())
        self.assertTrue(BlendPath(b"C:\\some\\file.blend").is_absolute())
        self.assertFalse(BlendPath(b"some/file.blend").is_absolute())

    def test_is_blendfile_relative(self):
        self.assertTrue(BlendPath(b"//some/file.blend").is_blendfile_relative())
        self.assertFalse(BlendPath(b"/some/file.blend").is_blendfile_relative())
        self.assertFalse(BlendPath(b"C:/some/file.blend").is_blendfile_relative())
        self.assertFalse(BlendPath(b"some/file.blend").is_blendfile_relative())

    def test_make_absolute(self):
        self.assertEqual(
            b"/root/to/some/file.blend",
            BlendPath(b"//some/file.blend").absolute(b"/root/to"),
        )
        self.assertEqual(
            b"/root/to/some/file.blend",
            BlendPath(b"some/file.blend").absolute(b"/root/to"),
        )
        self.assertEqual(
            b"/root/to/../some/file.blend",
            BlendPath(b"../some/file.blend").absolute(b"/root/to"),
        )
        self.assertEqual(
            b"/shared/some/file.blend",
            BlendPath(b"/shared/some/file.blend").absolute(b"/root/to"),
        )

    def test_slash(self):
        self.assertEqual(
            b"/root/and/parent.blend", BlendPath(b"/root/and") / b"parent.blend"
        )
        with self.assertRaises(ValueError):
            BlendPath(b"/root/and") / b"/parent.blend"

        self.assertEqual(
            b"/root/and/parent.blend", b"/root/and" / BlendPath(b"parent.blend")
        )
        with self.assertRaises(ValueError):
            b"/root/and" / BlendPath(b"/parent.blend")

        # On Windows+Python 3.5.4 this resulted in b'//root//parent.blend',
        # but only if the root is a single term (so not b'//root/and/').
        self.assertEqual(
            BlendPath(b"//root/parent.blend"), BlendPath(b"//root/") / b"parent.blend"
        )

    @unittest.skipIf(
        platform.system() == "Windows", "POSIX paths cannot be used on Windows"
    )
    def test_mkrelative_posix(self):
        self.assertEqual(
            b"//asset.png",
            BlendPath.mkrelative(
                Path("/path/to/asset.png"),
                PurePosixPath("/path/to/bfile.blend"),
            ),
        )
        self.assertEqual(
            b"//to/asset.png",
            BlendPath.mkrelative(
                Path("/path/to/asset.png"),
                PurePosixPath("/path/bfile.blend"),
            ),
        )
        self.assertEqual(
            b"//../of/asset.png",
            BlendPath.mkrelative(
                Path("/path/of/asset.png"),
                PurePosixPath("/path/to/bfile.blend"),
            ),
        )
        self.assertEqual(
            b"//../../path/of/asset.png",
            BlendPath.mkrelative(
                Path("/path/of/asset.png"),
                PurePosixPath("/some/weird/bfile.blend"),
            ),
        )
        self.assertEqual(
            b"//very/very/very/very/very/deep/asset.png",
            BlendPath.mkrelative(
                Path("/path/to/very/very/very/very/very/deep/asset.png"),
                PurePosixPath("/path/to/bfile.blend"),
            ),
        )
        self.assertEqual(
            b"//../../../../../../../../shallow/asset.png",
            BlendPath.mkrelative(
                Path("/shallow/asset.png"),
                PurePosixPath("/path/to/very/very/very/very/very/deep/bfile.blend"),
            ),
        )

    @unittest.skipIf(
        platform.system() != "Windows", "Windows paths cannot be used on POSIX"
    )
    def test_mkrelative_windows(self):
        self.assertEqual(
            b"//asset.png",
            BlendPath.mkrelative(
                Path("Q:/path/to/asset.png"),
                PureWindowsPath("Q:/path/to/bfile.blend"),
            ),
        )
        self.assertEqual(
            b"//to/asset.png",
            BlendPath.mkrelative(
                Path("Q:/path/to/asset.png"),
                PureWindowsPath("Q:/path/bfile.blend"),
            ),
        )
        self.assertEqual(
            b"//../of/asset.png",
            BlendPath.mkrelative(
                Path("Q:/path/of/asset.png"),
                PureWindowsPath("Q:/path/to/bfile.blend"),
            ),
        )
        self.assertEqual(
            b"//../../path/of/asset.png",
            BlendPath.mkrelative(
                Path("Q:/path/of/asset.png"),
                PureWindowsPath("Q:/some/weird/bfile.blend"),
            ),
        )
        self.assertEqual(
            b"//very/very/very/very/very/deep/asset.png",
            BlendPath.mkrelative(
                Path("Q:/path/to/very/very/very/very/very/deep/asset.png"),
                PureWindowsPath("Q:/path/to/bfile.blend"),
            ),
        )
        self.assertEqual(
            b"//../../../../../../../../shallow/asset.png",
            BlendPath.mkrelative(
                Path("Q:/shallow/asset.png"),
                PureWindowsPath("Q:/path/to/very/very/very/very/very/deep/bfile.blend"),
            ),
        )
        self.assertEqual(
            b"D:/path/to/asset.png",
            BlendPath.mkrelative(
                Path("D:/path/to/asset.png"),
                PureWindowsPath("Q:/path/to/bfile.blend"),
            ),
        )


class MakeAbsoluteTest(unittest.TestCase):
    def test_relative(self):
        my_dir = Path(__file__).absolute().parent
        cwd = os.getcwd()
        try:
            os.chdir(my_dir)
            self.assertEqual(
                my_dir / "blendfiles/Cube.btx",
                make_absolute(Path("blendfiles/Cube.btx")),
            )
        except Exception:
            os.chdir(cwd)
            raise

    @unittest.skipIf(platform.system() != "Windows", "This test uses drive letters")
    def test_relative_drive(self):
        cwd = os.getcwd()
        my_drive = Path(f"{Path(cwd).drive}/")
        self.assertEqual(
            my_drive / "blendfiles/Cube.btx",
            make_absolute(Path("/blendfiles/Cube.btx")),
        )

    def test_drive_letters(self):
        """PureWindowsPath should be accepted and work well on POSIX systems too."""
        in_path = PureWindowsPath("R:/wrongroot/oops/../../path/to/a/file")
        expect_path = Path("R:/path/to/a/file")
        self.assertNotEqual(
            expect_path, in_path, "pathlib should not automatically resolve ../"
        )
        self.assertEqual(expect_path, make_absolute(in_path))

    @unittest.skipIf(platform.system() == "Windows", "This test ignores drive letters")
    def test_dotdot_dotdot_posix(self):
        in_path = Path("/wrongroot/oops/../../path/to/a/file")
        expect_path = Path("/path/to/a/file")
        self.assertNotEqual(
            expect_path, in_path, "pathlib should not automatically resolve ../"
        )
        self.assertEqual(expect_path, make_absolute(in_path))

    @unittest.skipIf(platform.system() != "Windows", "This test uses drive letters")
    def test_dotdot_dotdot_windows(self):
        in_path = Path("Q:/wrongroot/oops/../../path/to/a/file")
        expect_path = Path("Q:/path/to/a/file")
        self.assertNotEqual(
            expect_path, in_path, "pathlib should not automatically resolve ../"
        )
        self.assertEqual(expect_path, make_absolute(in_path))

    @unittest.skipIf(platform.system() == "Windows", "This test ignores drive letters")
    def test_way_too_many_dotdot_posix(self):
        in_path = Path("/webroot/../../../../../etc/passwd")
        expect_path = Path("/etc/passwd")
        self.assertEqual(expect_path, make_absolute(in_path))

    @unittest.skipIf(platform.system() != "Windows", "This test uses drive letters")
    def test_way_too_many_dotdot_windows(self):
        in_path = Path("G:/webroot/../../../../../etc/passwd")
        expect_path = Path("G:/etc/passwd")
        self.assertEqual(expect_path, make_absolute(in_path))

    @unittest.skipIf(
        platform.system() == "Windows",
        "Symlinks on Windows require Administrator rights",
    )
    def test_symlinks(self):
        with tempfile.TemporaryDirectory(suffix="-bat-symlink-test") as tmpdir_str:
            tmpdir = Path(tmpdir_str)

            orig_path = tmpdir / "some_file.txt"
            with orig_path.open("w") as outfile:
                outfile.write("this file exists now")

            symlink = tmpdir / "subdir" / "linked.txt"
            symlink.parent.mkdir()
            symlink.symlink_to(orig_path)

            self.assertEqual(
                symlink, make_absolute(symlink), "Symlinks should not be resolved"
            )

    @unittest.skipIf(
        platform.system() != "Windows",
        "Drive letters mapped to network share can only be tested on Windows",
    )
    @unittest.skip(
        "Mapped drive letter testing should be mocked, but that is hard to do"
    )
    def test_mapped_drive_letters(self):
        pass

    def test_path_types(self):
        platorm_path = type(PurePath())
        self.assertIsInstance(
            make_absolute(PureWindowsPath("/some/path")), platorm_path
        )
        self.assertIsInstance(make_absolute(PurePosixPath("/some/path")), platorm_path)


class StripRootTest(unittest.TestCase):
    def test_windows_paths(self):
        self.assertEqual(PurePosixPath(), strip_root(PureWindowsPath()))
        self.assertEqual(
            PurePosixPath("C/Program Files/Blender"),
            strip_root(PureWindowsPath("C:/Program Files/Blender")),
        )
        self.assertEqual(
            PurePosixPath("C/Program Files/Blender"),
            strip_root(PureWindowsPath("C:\\Program Files\\Blender")),
        )
        self.assertEqual(
            PurePosixPath("C/Program Files/Blender"),
            strip_root(PureWindowsPath("C\\Program Files\\Blender")),
        )

    def test_posix_paths(self):
        self.assertEqual(PurePosixPath(), strip_root(PurePosixPath()))
        self.assertEqual(
            PurePosixPath("C/path/to/blender"),
            strip_root(PurePosixPath("C:/path/to/blender")),
        )
        self.assertEqual(
            PurePosixPath("C/path/to/blender"),
            strip_root(PurePosixPath("C/path/to/blender")),
        )
        self.assertEqual(
            PurePosixPath("C/path/to/blender"),
            strip_root(PurePosixPath("/C/path/to/blender")),
        )
