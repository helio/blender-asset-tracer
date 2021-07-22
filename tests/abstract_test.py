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
import logging
import pathlib
import unittest

from blender_asset_tracer import blendfile

logging.basicConfig(
    format="%(asctime)-15s %(levelname)8s %(name)s %(message)s", level=logging.INFO
)


class AbstractBlendFileTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.blendfiles = pathlib.Path(__file__).with_name("blendfiles")

    def setUp(self):
        self.bf = None

    def tearDown(self):
        if self.bf is not None:
            self.bf.close()
        self.bf = None
        blendfile.close_all_cached()
