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
from importlib.resources import path
import json
import pathlib
import platform

import responses

from tests.abstract_test import AbstractBlendFileTest
from blender_asset_tracer.pack.shaman import transfer

httpmock = responses.RequestsMock()


class ShamanTransferTest(AbstractBlendFileTest):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.test_file1 = cls.blendfiles / "linked_cube_compressed.blend"
        cls.test_file2 = cls.blendfiles / "basic_file.blend"
        cls.expected_checksums = {
            cls.test_file1: "3c525e3a01ece11f26ded1e05e43284c4cce575c8074b97c6bdbc414fa2802ab",
            cls.test_file2: "d5283988d95f259069d4cd3c25a40526090534b8d188577b6c6fb36c3d481454",
        }
        cls.file_sizes = {
            cls.test_file1: cls.test_file1.stat().st_size,
            cls.test_file2: cls.test_file2.stat().st_size,
        }
        cls.packed_names = {
            cls.test_file1: pathlib.PurePosixPath("path/in/pack/test1.blend"),
            cls.test_file2: pathlib.PurePosixPath("path/in/pack/test2.blend"),
        }

    def assertValidCheckoutDef(self, request_body: bytes):
        payload = json.loads(request_body)

        # We don't care much about the order, so compare as set.
        actual_specs = {transfer.ShamanFileSpecWithPath(sha=f['sha'], size=f['size'], path=f['path'])
            for f in payload['files']}
        expect_specs = set()
        for filepath in [self.test_file1, self.test_file2]:
            expect_specs.add(transfer.ShamanFileSpecWithPath(
                sha=self.expected_checksums[filepath],
                size=self.file_sizes[filepath],
                path=self.packed_names[filepath].as_posix()))
        self.assertEqual(expect_specs, actual_specs)

    def assertValidCheckoutRequirement(self, request_body: bytes):
        payload = json.loads(request_body)

        # We don't care much about the order, so compare as set.
        actual_specs = {transfer.ShamanFileSpec(sha=f['sha'], size=f['size'])
            for f in payload['files']}
        expect_specs = set()
        for filepath in [self.test_file1, self.test_file2]:
            expect_specs.add(transfer.ShamanFileSpec(
                sha=self.expected_checksums[filepath],
                size=self.file_sizes[filepath]))
        self.assertEqual(expect_specs, actual_specs)

    @httpmock.activate
    def test_checkout_happy(self):
        checksum1 = self.expected_checksums[self.test_file1]
        fsize1 = self.file_sizes[self.test_file1]

        def mock_requirements(request):
            self.assertEqual("application/json", request.headers["Content-Type"])
            self.assertValidCheckoutRequirement(request.body)

            response =  json.dumps({
                'files': [
                    {'sha': self.expected_checksums[filepath],
                     'size': self.file_sizes[filepath],
                     'status': 'unknown',
                     }
                    for filepath in [self.test_file1, self.test_file2]
                ]
            })
            return 200, {"Content-Type": "application/json"}, response

        def mock_checkout_create(request):
            self.assertEqual("application/json", request.headers["Content-Type"])
            self.assertValidCheckoutDef(request.body)
            return 204, {"Content-Type": "application/json"}, ""

        httpmock.add_callback(
            "POST",
            "http://unittest.local:1234/shaman/checkout/requirements",
            callback=mock_requirements,
        )

        httpmock.add(
            "POST", "http://unittest.local:1234/shaman/files/%s/%d" % (checksum1, fsize1)
        )
        httpmock.add_callback(
            "POST",
            "http://unittest.local:1234/shaman/checkout/create",
            callback=mock_checkout_create,
        )

        trans = transfer.ShamanTransferrer(
            "", self.blendfiles, "http://unittest.local:1234/shaman/", "projectname/DA-JOB-ID"
        )

        trans.start()
        trans.queue_copy(self.test_file1, self.packed_names[self.test_file1])
        trans.queue_copy(self.test_file2, self.packed_names[self.test_file2])
        trans.done_and_join()

        self.assertFalse(trans.has_error, trans.error_message())
