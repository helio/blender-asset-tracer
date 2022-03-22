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
import collections
from dataclasses import dataclass, asdict
import logging
import pathlib
import random
import typing

import requests

import blender_asset_tracer.pack.transfer as bat_transfer
from blender_asset_tracer import bpathlib

MAX_DEFERRED_PATHS = 8
MAX_FAILED_PATHS = 8

# See flamenco-manager.yaml in Flamenco v3, schema ShamanFileStatus.
response_file_unknown = "unknown"
response_already_uploading = "uploading"
response_stored = "stored"

@dataclass(eq=True, frozen=True)
class FilePaths:
    abspath: pathlib.Path
    """The absolute path, for easy access to the file itself."""
    relpath: pathlib.PurePosixPath
    """The path relative to the pack, for communication with Shaman."""

@dataclass(eq=True, frozen=True)
class ShamanFileSpec:
    sha: str   # SHA256 checksum.
    size: int  # File size in bytes.

@dataclass(eq=True, frozen=True)
class ShamanFileSpecWithStatus:
    sha: str   # SHA256 checksum.
    size: int  # File size in bytes.
    status: str  # See response_xxxx above.

    def spec(self) -> ShamanFileSpec:
        return ShamanFileSpec(sha=self.sha, size=self.size)

@dataclass(eq=True, frozen=True)
class ShamanFileSpecWithPath:
    sha: str   # SHA256 checksum.
    size: int  # File size in bytes.
    path: pathlib.PurePosixPath  # File path relative to the checkout root.

    def spec(self) -> ShamanFileSpec:
        return ShamanFileSpec(sha=self.sha, size=self.size)

    def asjson(self) -> dict:
        """Returns a json-serialisable dictionary."""
        return {
            'sha': self.sha,
            'size': self.size,
            'path': self.path.as_posix(),
        }


class ShamanTransferrer(bat_transfer.FileTransferer):
    """Sends files to a Shaman server."""

    class AbortUpload(Exception):
        """Raised from the upload callback to abort an upload."""

    def __init__(
        self,
        auth_token: str,
        project_root: pathlib.Path,
        shaman_endpoint: str,
        checkout_path: str,
    ) -> None:
        from . import client

        super().__init__()
        self.client = client.ShamanClient(auth_token, shaman_endpoint)
        self.project_root = project_root
        self.checkout_path = checkout_path
        self.log = logging.getLogger(__name__)

        self._spec_to_paths = {}  # type: typing.Dict[ShamanFileSpec, FilePaths]

        self.uploaded_files = 0
        self.uploaded_bytes = 0

    # noinspection PyBroadException
    def run(self) -> None:
        try:
            self.uploaded_files = 0
            self.uploaded_bytes = 0

            # Construct the Shaman Checkout Definition file.
            # This blocks until we know the entire list of files to transfer.
            (
                shaman_file_specs,
                delete_when_done,
            ) = self._create_checkout_definition()
            if not shaman_file_specs:
                # An error has already been logged.
                return

            self.log.info("Feeding %d files to the Shaman", len(shaman_file_specs))
            if self.log.isEnabledFor(logging.INFO):
                for spec in shaman_file_specs:
                    file_paths = self._spec_to_paths[spec.spec()]
                    self.log.info("   - %s", file_paths.relpath)

            # Try to upload all the files.
            failed_paths = set()  # type: typing.Set[ShamanFileSpecWithPath]
            max_tries = 50
            for try_index in range(max_tries):
                # Send the file to the Shaman and see what we still need to send there.
                specs_without_path = [spec.spec() for spec in shaman_file_specs]
                to_upload = self._send_checkout_def_to_shaman(specs_without_path)
                if to_upload is None:
                    # An error has already been logged.
                    return

                if not to_upload:
                    break

                # Send the files that still need to be sent.
                self.log.info("Upload attempt %d", try_index + 1)
                failed_paths = self._upload_files(to_upload)
                if not failed_paths:
                    break

                # Having failed paths at this point is expected when multiple
                # clients are sending the same files. Instead of retrying on a
                # file-by-file basis, we just re-send the checkout definition
                # file to the Shaman and obtain a new list of files to upload.

            if failed_paths:
                self.log.error("Aborting upload due to too many failures")
                self.error_set(
                    "Giving up after %d attempts to upload the files" % max_tries
                )
                return

            self.log.info("All files uploaded succesfully")
            self._request_checkout(shaman_file_specs)

            # Delete the files that were supposed to be moved.
            for src in delete_when_done:
                self.delete_file(src)

        except Exception as ex:
            # We have to catch exceptions in a broad way, as this is running in
            # a separate thread, and exceptions won't otherwise be seen.
            self.log.exception("Error transferring files to Shaman")
            self.error_set("Unexpected exception transferring files to Shaman: %s" % ex)

    # noinspection PyBroadException
    def _create_checkout_definition(
        self,
    ) -> typing.Tuple[typing.List[ShamanFileSpecWithPath], typing.List[pathlib.Path]]:
        """Create the checkout definition file for this BAT pack.

        :returns: the checkout definition and list of paths to delete when the
            transfer is complete.

        If there was an error and file transfer was aborted, the checkout
        definition will be empty.
        """
        from . import cache

        filespecs = [] # type: typing.List[ShamanFileSpecWithPath]
        delete_when_done = []  # type: typing.List[pathlib.Path]

        for src, dst, act in self.iter_queue():
            try:
                checksum = cache.compute_cached_checksum(src)
                filesize = src.stat().st_size
                # relpath = dst.relative_to(self.project_root)
                relpath = bpathlib.strip_root(dst)

                filespec = ShamanFileSpecWithPath(
                    sha=checksum,
                    size=filesize,
                    path=relpath,
                )
                filespecs.append(filespec)
                self._spec_to_paths[filespec.spec()] = FilePaths(abspath=src, relpath=relpath)

                if act == bat_transfer.Action.MOVE:
                    delete_when_done.append(src)
            except Exception:
                # We have to catch exceptions in a broad way, as this is running in
                # a separate thread, and exceptions won't otherwise be seen.
                msg = "Error transferring %s to %s" % (src, dst)
                self.log.exception(msg)
                # Put the files to copy back into the queue, and abort. This allows
                # the main thread to inspect the queue and see which files were not
                # copied. The one we just failed (due to this exception) should also
                # be reported there.
                self.queue.put((src, dst, act))
                self.error_set(msg)
                return [], delete_when_done

        cache.cleanup_cache()
        return filespecs, delete_when_done

    def _send_checkout_def_to_shaman(
        self, shaman_file_specs: typing.List[ShamanFileSpec],
    ) -> typing.Optional[typing.Deque[ShamanFileSpecWithPath]]:
        """Send the checkout definition file to the Shaman.

        :return: An iterable of paths (relative to the project root) that still
            need to be uploaded, or None if there was an error.
        """

        resp = self.client.post(
            "checkout/requirements",
            json={'files': [asdict(spec) for spec in shaman_file_specs]},
            timeout=15,
        )
        if resp.status_code >= 300:
            msg = "Error from Shaman, code %d: %s" % (resp.status_code, resp.text)
            self.log.error(msg)
            self.error_set(msg)
            return None


        to_upload = collections.deque()  # type: collections.deque
        payload = resp.json()
        for file_info in payload['files']:
            try:
                spec_with_status = ShamanFileSpecWithStatus(**file_info)
            except TypeError:  # Thrown for missing or extra keyword arguments.
                msg = "Unknown response from Shaman: %r" % file_info
                self.log.error(msg)
                self.error_set(msg)
                return None

            file_spec = spec_with_status.spec()
            try:
                pathinfo = self._spec_to_paths[file_spec]
            except KeyError:
                msg = "Shaman requested path we did not intend to upload: %r" % spec_with_status
                self.log.error(msg)
                self.error_set(msg)
                return None

            self.log.debug("   %s: %s", spec_with_status.status, pathinfo.relpath)

            spec_with_path = ShamanFileSpecWithPath(
                sha=spec_with_status.sha,
                size=spec_with_status.size,
                path=pathinfo.relpath,
            )
            if spec_with_status.status == response_file_unknown:
                to_upload.appendleft(spec_with_path)
            elif spec_with_status.status == response_already_uploading:
                to_upload.append(spec_with_path)
            else:
                msg = "Unknown status in response from Shaman: %r" % spec_with_status
                self.log.error(msg)
                self.error_set(msg)
                return None

        return to_upload

    def _upload_files(self, to_upload: typing.Deque[ShamanFileSpecWithPath]) -> typing.Set[ShamanFileSpecWithPath]:
        """Actually upload the files to Shaman.

        Returns the set of files that we did not upload.
        """
        if not to_upload:
            self.log.info("All files are at the Shaman already")
            self.report_transferred(0)
            return set()

        failed_specs = set()  # type: typing.Set[ShamanFileSpecWithPath]
        deferred_specs = set()  # type: typing.Set[ShamanFileSpecWithPath]

        def defer(filespec: ShamanFileSpecWithPath):
            nonlocal to_upload

            self.log.info(
                "   %s deferred (already being uploaded by someone else)", filespec.path
            )
            deferred_specs.add(filespec)

            # Instead of deferring this one file, randomize the files to upload.
            # This prevents multiple deferrals when someone else is uploading
            # files from the same project (because it probably happens alphabetically).
            all_files = list(to_upload)
            random.shuffle(all_files)
            to_upload = collections.deque(all_files)

        self.log.info(
            "Going to upload %d of %d files", len(to_upload), len(self._spec_to_paths)
        )
        while to_upload:
            # After too many failures, just retry to get a fresh set of files to upload.
            if len(failed_specs) > MAX_FAILED_PATHS:
                self.log.info("Too many failures, going to abort this iteration")
                failed_specs.update(to_upload)
                return failed_specs

            filespec = to_upload.popleft()
            filepaths = self._spec_to_paths[filespec.spec()]
            self.log.info("   %s", filespec.path)

            headers = {
                "X-Shaman-Original-Filename": filespec.path.as_posix(),
            }
            # Let the Shaman know whether we can defer uploading this file or not.
            can_defer = (
                len(deferred_specs) < MAX_DEFERRED_PATHS
                and filespec not in deferred_specs
                and len(to_upload)
            )
            if can_defer:
                headers["X-Shaman-Can-Defer-Upload"] = "true"

            url = "files/%s/%d" % (filespec.sha, filespec.size)
            try:
                with filepaths.abspath.open("rb") as infile:
                    resp = self.client.post(url, data=infile, headers=headers)

            except requests.ConnectionError as ex:
                if can_defer:
                    # Closing the connection with an 'X-Shaman-Can-Defer-Upload: true' header
                    # indicates that we should defer the upload. Requests doesn't give us the
                    # reply, even though it might be written by the Shaman before it closed the
                    # connection.
                    defer(filespec)
                else:
                    self.log.info(
                        "   %s could not be uploaded, might retry later: %s", filespec.path, ex
                    )
                    failed_specs.add(filespec)
                continue

            if resp.status_code == 208:
                # For small files we get the 208 response, because the server closes the
                # connection after we sent the entire request. For bigger files the server
                # responds sooner, and Requests gives us the above ConnectionError.
                if can_defer:
                    defer(filespec)
                else:
                    self.log.info("   %s skipped (already existed on the server)", filespec)
                continue

            if resp.status_code >= 300:
                msg = "Error from Shaman uploading %s, code %d: %s" % (
                    filepaths.abspath,
                    resp.status_code,
                    resp.text,
                )
                self.log.error(msg)
                self.error_set(msg)
                return failed_specs

            failed_specs.discard(filespec)
            self.uploaded_files += 1
            file_size = filepaths.abspath.stat().st_size
            self.uploaded_bytes += file_size
            self.report_transferred(file_size)

        if not failed_specs:
            self.log.info(
                "Done uploading %d bytes in %d files",
                self.uploaded_bytes,
                self.uploaded_files,
            )
        else:
            self.log.info(
                "Uploaded %d bytes in %d files so far",
                self.uploaded_bytes,
                self.uploaded_files,
            )

        return failed_specs

    def report_transferred(self, bytes_transferred: int):
        if self._abort.is_set():
            self.log.warning("Interrupting ongoing upload")
            raise self.AbortUpload("interrupting ongoing upload")
        super().report_transferred(bytes_transferred)

    def _request_checkout(self, shaman_file_specs: typing.List[ShamanFileSpecWithPath]):
        """Ask the Shaman to create a checkout of this BAT pack."""

        if not self.checkout_path:
            self.log.warning("NOT requesting checkout at Shaman")
            return

        self.log.info(
            "Requesting checkout at Shaman for checkout_path=%r", self.checkout_path
        )
        resp = self.client.post(
            "checkout/create",
            json={
                "files": [spec.asjson() for spec in shaman_file_specs],
                "checkoutPath": self.checkout_path,
            },
        )
        if resp.status_code >= 300:
            msg = "Error from Shaman, code %d: %s" % (resp.status_code, resp.text)
            self.log.error(msg)
            self.error_set(msg)
            return

        self.log.info("Response from Shaman, code %d: %s", resp.status_code, resp.text)
