# ***** BEGIN GPL LICENSE BLOCK *****
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software Foundation,
# Inc., 59 Temple Place - Suite 330, Boston, MA  02111-1307, USA.
#
# ***** END GPL LICENCE BLOCK *****
#
# (c) 2019, Blender Foundation - Sybren A. Stüvel
import zipfile
from tests.test_pack import AbstractPackTest

from blender_asset_tracer.pack import zipped


class ZippedPackTest(AbstractPackTest):
    def test_basic_file(self):
        infile = self.blendfiles / "basic_file_ñønæščii.blend"
        zippath = self.tpath / "target.zip"
        with zipped.ZipPacker(infile, infile.parent, zippath) as packer:
            packer.strategise()
            packer.execute()

        self.assertTrue(zippath.exists())
        with zipfile.ZipFile(str(zippath)) as inzip:
            inzip.testzip()
            self.assertEqual(
                {"pack-info.txt", "basic_file_ñønæščii.blend"}, set(inzip.namelist())
            )
