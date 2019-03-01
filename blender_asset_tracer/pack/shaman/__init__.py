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
from blender_asset_tracer.pack.shaman.transfer import ShamanTransferrer

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

        :param target: mock target '/' to construct project-relative paths.
        :param endpoint: URL of the Shaman endpoint.
        """
        super().__init__(bfile, project, target, **kwargs)
        self.checkout_id = checkout_id
        self.shaman_endpoint = endpoint
        self._checkout_location = ''

    def _get_auth_token(self) -> str:
        # TODO: get a token from the Flamenco Server.
        log.warning('Using temporary hack to get auth token from Shaman')
        resp = requests.get(urllib.parse.urljoin(self.shaman_endpoint, 'get-token'))
        return resp.text

    def _create_file_transferer(self) -> bat_transfer.FileTransferer:
        # TODO: pass self._get_auth_token itself, so that the Transferer will be able to
        # decide when to get this token (and how many times).
        auth_token = self._get_auth_token()
        return ShamanTransferrer(auth_token, self.project, self.shaman_endpoint, self.checkout_id)

    def _make_target_path(self, target: str) -> pathlib.PurePath:
        return pathlib.PurePosixPath('/')

    def _on_file_transfer_finished(self, *, file_transfer_completed: bool):
        super()._on_file_transfer_finished(file_transfer_completed=file_transfer_completed)

        assert isinstance(self._file_transferer, ShamanTransferrer)
        self._checkout_location = self._file_transferer.checkout_location

    @property
    def checkout_location(self) -> str:
        """Return the checkout location of the packed blend file."""
        return self._checkout_location

    @property
    def output_path(self) -> pathlib.PurePath:
        """The path of the packed blend file in the target directory."""
        assert self._output_path is not None

        checkout_location = pathlib.PurePosixPath(self._checkout_location)
        rel_output = self._output_path.relative_to(self._target_path)
        return checkout_location / rel_output

    def execute(self):
        try:
            super().execute()
        except requests.exceptions.ConnectionError as ex:
            log.exception('Error communicating with Shaman')
            self.abort(str(ex))
            self._check_aborted()
