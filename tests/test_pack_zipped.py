import zipfile
from test_pack import AbstractPackTest

from blender_asset_tracer.pack import zipped


class ZippedPackTest(AbstractPackTest):
    def test_basic_file(self):
        infile = self.blendfiles / 'basic_file_ñønæščii.blend'
        zippath = self.tpath / 'target.zip'
        with zipped.ZipPacker(infile, infile.parent, zippath) as packer:
            packer.strategise()
            packer.execute()

        self.assertTrue(zippath.exists())
        with zipfile.ZipFile(str(zippath)) as inzip:
            inzip.testzip()
            self.assertEqual({'pack-info.txt', 'basic_file_ñønæščii.blend'}, set(inzip.namelist()))
