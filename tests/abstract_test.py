import pathlib
import unittest


class AbstractBlendFileTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.blendfiles = pathlib.Path(__file__).with_name('blendfiles')

    def setUp(self):
        self.bf = None

    def tearDown(self):
        if self.bf:
            self.bf.close()
