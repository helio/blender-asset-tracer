import pathlib
import tempfile
import shutil

from blender_asset_tracer import blendfile
from tests.abstract_test import AbstractBlendFileTest

from blender_asset_tracer import compressor


class CompressorTest(AbstractBlendFileTest):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        tempdir = pathlib.Path(self.temp.name)
        self.srcdir = tempdir / "src"
        self.destdir = tempdir / "dest"

        self.srcdir.mkdir()
        self.destdir.mkdir()

    def tearDown(self):
        self.temp.cleanup()

    def _test(self, filename: str, source_must_remain: bool):
        """Do a move/copy test.

        The result should be the same, regardless of whether the
        source file was already compressed or not.
        """
        # Make a copy we can move around without moving the actual file in
        # the source tree.
        srcfile = self.srcdir / filename
        destfile = self.destdir / filename
        srcfile.parent.mkdir(parents=True, exist_ok=True)
        destfile.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(str(self.blendfiles / filename), str(srcfile))

        if source_must_remain:
            compressor.copy(srcfile, destfile)
        else:
            compressor.move(srcfile, destfile)

        self.assertEqual(source_must_remain, srcfile.exists())
        self.assertTrue(destfile.exists())

        if destfile.suffix == ".blend":
            self.bf = blendfile.BlendFile(destfile)
            self.assertTrue(self.bf.is_compressed)
            return

        with destfile.open("rb") as infile:
            magic = infile.read(3)
        if destfile.suffix == ".jpg":
            self.assertEqual(
                b"\xFF\xD8\xFF", magic, "Expected %s to be a JPEG" % destfile
            )
        else:
            self.assertNotEqual(
                b"\x1f\x8b", magic[:2], "Expected %s to be NOT compressed" % destfile
            )

    def test_move_already_compressed(self):
        self._test("basic_file_ñønæščii.blend", False)

    def test_move_compress_on_the_fly(self):
        self._test("basic_file.blend", False)

    def test_copy_already_compressed(self):
        self._test("basic_file_ñønæščii.blend", True)

    def test_copy_zstandard_compressed(self):
        self._test("basic_file_zstandard.blend", True)

    def test_copy_compress_on_the_fly(self):
        self._test("basic_file.blend", True)

    def test_move_jpeg(self):
        self._test("textures/Bricks/brick_dotted_04-color.jpg", False)
