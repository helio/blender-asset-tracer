import logging
import pathlib
import unittest

from blender_asset_tracer import blendfile


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
        if self.bf is not None:
            self.bf.close()
        self.bf = None
        blendfile.close_all_cached()
