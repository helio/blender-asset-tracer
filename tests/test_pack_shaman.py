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
import pathlib

import responses

from test_pack import AbstractPackTest
from blender_asset_tracer.pack import shaman

httpmock = responses.RequestsMock()


class ShamanPackTest(AbstractPackTest):
    @httpmock.activate
    def test_all_files_already_uploaded(self):
        infile = self.blendfiles / 'basic_file_ñønæščii.blend'

        packer = shaman.ShamanPacker(infile, infile.parent, '/',
                                     endpoint='http://shaman.local',
                                     checkout_id='DA-JOBBY-ID')

        # Temporary hack
        httpmock.add('GET', 'http://shaman.local/get-token', body='AUTH-TOKEN')

        # Just fake that everything is already available on the server.
        httpmock.add('POST', 'http://shaman.local/checkout/requirements', body='')
        httpmock.add('POST', 'http://shaman.local/checkout/create/DA-JOBBY-ID',
                     body='DA/-JOBBY-ID')

        with packer:
            packer.strategise()
            packer.execute()

        self.assertEqual(pathlib.PurePosixPath('DA/-JOBBY-ID/basic_file_ñønæščii.blend'),
                         packer.output_path)
