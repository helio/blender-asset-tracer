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
import json
import pathlib
from unittest import mock

from tests.abstract_test import AbstractBlendFileTest
from blender_asset_tracer.pack.shaman import cache


class AbstractChecksumTest(AbstractBlendFileTest):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.test_file = cls.blendfiles / 'linked_cube_compressed.blend'
        cls.expected_checksum = '3c525e3a01ece11f26ded1e05e43284c4cce575c8074b97c6bdbc414fa2802ab'


class ChecksumTest(AbstractChecksumTest):
    def test_checksum(self):
        self.assertEqual(self.expected_checksum, cache.compute_checksum(self.test_file))


class CachedChecksumTest(AbstractChecksumTest):
    @mock.patch('blender_asset_tracer.pack.shaman.cache._cache_path')
    @mock.patch('blender_asset_tracer.pack.shaman.cache.compute_checksum')
    def test_cache_invalid_json(self, mock_compute_checksum, mock_cache_path):
        mock_path = mock.MagicMock(spec=pathlib.Path)
        mock_path.open().__enter__().read.return_value = 'je moeder'
        mock_cache_path.return_value = mock_path

        mock_compute_checksum.return_value = 'computed-checksum'

        checksum = cache.compute_cached_checksum(self.test_file)
        self.assertEqual('computed-checksum', checksum)

    @mock.patch('blender_asset_tracer.pack.shaman.cache._cache_path')
    @mock.patch('blender_asset_tracer.pack.shaman.cache.compute_checksum')
    def test_cache_valid_json(self, mock_compute_checksum, mock_cache_path):
        stat = self.test_file.stat()
        cache_info = {
            'checksum': 'cached-checksum',
            'file_mtime': stat.st_mtime + 0.0001,  # mimick a slight clock skew
            'file_size': stat.st_size,
        }

        mock_path = mock.MagicMock(spec=pathlib.Path)
        mock_path.open().__enter__().read.return_value = json.dumps(cache_info)
        mock_cache_path.return_value = mock_path

        mock_compute_checksum.return_value = 'computed-checksum'

        checksum = cache.compute_cached_checksum(self.test_file)
        self.assertEqual('cached-checksum', checksum)

    @mock.patch('blender_asset_tracer.pack.shaman.cache._cache_path')
    @mock.patch('blender_asset_tracer.pack.shaman.cache.compute_checksum')
    def test_cache_not_exists(self, mock_compute_checksum, mock_cache_path):
        mock_path = mock.MagicMock(spec=pathlib.Path)
        mock_path.open.side_effect = [
            FileNotFoundError('Testing absent cache file'),
            FileExistsError('Testing I/O error when writing'),
        ]
        mock_cache_path.return_value = mock_path

        mock_compute_checksum.return_value = 'computed-checksum'

        # This should not raise the FileExistsError
        checksum = cache.compute_cached_checksum(self.test_file)
        self.assertEqual('computed-checksum', checksum)
