import logging
import pathlib
import unittest


class AbstractBlendFileTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.blendfiles = pathlib.Path(__file__).with_name('blendfiles')
        logging.basicConfig(
            format='%(asctime)-15s %(levelname)8s %(name)s %(message)s',
            level=logging.INFO)

    def setUp(self):
        self.bf = None

    def tearDown(self):
        if self.bf:
            self.bf.close()
