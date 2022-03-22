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
import os
import pathlib
import typing
import urllib.parse

import requests

import blender_asset_tracer.pack as bat_pack
import blender_asset_tracer.pack.transfer as bat_transfer

from .transfer import ShamanTransferrer
from .client import ShamanClient

log = logging.getLogger(__name__)


class ShamanPacker(bat_pack.Packer):
    """Creates BAT Packs on a Shaman server."""

    def __init__(
        self,
        bfile: pathlib.Path,
        project: pathlib.Path,
        target: str,
        endpoint: str,
        checkout_path: str,
        **kwargs
    ) -> None:
        """Constructor

        :param target: mock target '/' to construct project-relative paths.
        :param endpoint: URL of the Shaman endpoint.
        """
        super().__init__(bfile, project, target, **kwargs)
        self.checkout_path = checkout_path
        self.shaman_endpoint = endpoint

    def _get_auth_token(self) -> str:
        # TODO: get a token from the Flamenco Server.
        token_from_env = os.environ.get("SHAMAN_JWT_TOKEN")
        if token_from_env:
            return token_from_env

        # This code was used in Flamenco v2 to aid in development of the JWT
        # authentication flow. Flamenco v3's authentication system still needs
        # to be designed, so for now just use unauthenticated calls.
        #
        # log.warning(
        #     "Using temporary hack to get auth token from Shaman, "
        #     "set SHAMAN_JTW_TOKEN to prevent"
        # )
        # unauth_shaman = ShamanClient("", self.shaman_endpoint)
        # resp = unauth_shaman.get("get-token", timeout=10)
        # resp.raise_for_status()
        # return resp.text
        return ""

    def _create_file_transferer(self) -> bat_transfer.FileTransferer:
        # TODO: pass self._get_auth_token itself, so that the Transferer will be able to
        # decide when to get this token (and how many times).
        auth_token = self._get_auth_token()
        return ShamanTransferrer(
            auth_token, self.project, self.shaman_endpoint, self.checkout_path
        )

    def _make_target_path(self, target: str) -> pathlib.PurePath:
        return pathlib.PurePosixPath("/")

    def _on_file_transfer_finished(self, *, file_transfer_completed: bool):
        super()._on_file_transfer_finished(
            file_transfer_completed=file_transfer_completed
        )
        assert isinstance(self._file_transferer, ShamanTransferrer)

    @property
    def output_path(self) -> pathlib.PurePath:
        """The path of the packed blend file in the target directory."""
        assert self._output_path is not None

        checkout_location = pathlib.PurePosixPath(self.checkout_path)
        rel_output = self._output_path.relative_to(self._target_path)
        return checkout_location / rel_output

    def execute(self):
        try:
            super().execute()
        except requests.exceptions.ConnectionError as ex:
            log.exception("Error communicating with Shaman")
            self.abort(str(ex))
            self._check_aborted()


def parse_endpoint(shaman_url: str) -> typing.Tuple[str, str]:
    """Convert shaman://hostname/path#checkoutID into endpoint URL + checkout ID."""

    urlparts = urllib.parse.urlparse(str(shaman_url))

    if urlparts.scheme in {"shaman", "shaman+https"}:
        scheme = "https"
    elif urlparts.scheme == "shaman+http":
        scheme = "http"
    else:
        raise ValueError(
            "Invalid scheme %r, choose shaman:// or shaman+http://", urlparts.scheme
        )

    checkout_path = urllib.parse.unquote(urlparts.fragment)

    path = urlparts.path or "/"
    new_urlparts = (scheme, urlparts.netloc, path, *urlparts[3:-1], "")
    endpoint = urllib.parse.urlunparse(new_urlparts)

    return endpoint, checkout_path
