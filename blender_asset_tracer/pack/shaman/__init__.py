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
"""Shaman Client interface."""
import logging
import pathlib
import urllib.parse

import requests

import blender_asset_tracer.pack as bat_pack
import blender_asset_tracer.pack.transfer as bat_transfer

log = logging.getLogger(__name__)


class ShamanPacker(bat_pack.Packer):
    """Creates BAT Packs on a Shaman server."""

    def __init__(self,
                 bfile: pathlib.Path,
                 project: pathlib.Path,
                 target: str,
                 endpoint: str,
                 checkout_id: str,
                 **kwargs) -> None:
        """Constructor

        :param endpoint: URL of the Shaman endpoint.
        """
        super().__init__(bfile, project, target, **kwargs)
        self.checkout_id = checkout_id
        self.shaman_endpoint = endpoint

    def _get_auth_token(self) -> str:
        # TODO: get a token from the Flamenco Server.
        log.warning('Using temporary hack to get auth token from Shaman')
        resp = requests.get(urllib.parse.urljoin(self.shaman_endpoint, 'get-token'))
        return resp.text

    def _create_file_transferer(self) -> bat_transfer.FileTransferer:
        from . import transfer

        # TODO: pass self._get_auth_token itself, so that the Transferer will be able to
        # decide when to get this token (and how many times).
        auth_token = self._get_auth_token()
        return transfer.ShamanTransferrer(auth_token, self.project, self.shaman_endpoint,
                                          self.checkout_id)

    def _make_target_path(self, target: str) -> pathlib.PurePath:
        return pathlib.PurePosixPath('/')
