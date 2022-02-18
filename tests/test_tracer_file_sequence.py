from tests.abstract_test import AbstractBlendFileTest

from blender_asset_tracer.trace import file_sequence


class ExpandFileSequenceTest(AbstractBlendFileTest):
    def setUp(self):
        super().setUp()
        self.imgseq = [
            self.blendfiles / ("imgseq/%06d.png" % num) for num in range(210, 215)
        ]

    def test_glob(self):
        path = self.blendfiles / "imgseq/*.png"
        actual = list(file_sequence.expand_sequence(path))
        self.assertEqual(self.imgseq, actual)

    def test_first_file(self):
        path = self.blendfiles / "imgseq/000210.png"
        actual = list(file_sequence.expand_sequence(path))
        self.assertEqual(self.imgseq, actual)

    def test_udim_sequence(self):
        path = self.blendfiles / "udim/cube_UDIM.color.<UDIM>.png"
        actual = list(file_sequence.expand_sequence(path))
        imgseq = [
            self.blendfiles / ("udim/cube_UDIM.color.%04d.png" % num) for num in range(1001, 1004)
        ]
        self.assertEqual(imgseq, actual)

    def test_nonexistent(self):
        path = self.blendfiles / "nonexistant"
        with self.assertRaises(file_sequence.DoesNotExist) as raises:
            for result in file_sequence.expand_sequence(path):
                self.fail("unexpected result %r" % result)

        self.assertEqual(path, raises.exception.path)

    def test_non_sequence_file(self):
        path = self.blendfiles / "imgseq/LICENSE.txt"
        actual = list(file_sequence.expand_sequence(path))
        self.assertEqual([path], actual)
