"""Amazon S3-compatible uploader."""
import typing

import hashlib
import logging
import pathlib
import threading

from . import Packer, transfer

log = logging.getLogger(__name__)


def compute_md5(filepath: pathlib.Path) -> str:
    hasher = hashlib.md5()
    with filepath.open('rb') as infile:
        while True:
            block = infile.read(10240)
            if not block:
                break
            hasher.update(block)
    md5 = hasher.hexdigest()
    return md5


class S3Packer(Packer):
    """Creates BAT Packs on S3-compatible storage."""

    def __init__(self, *args, endpoint, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        import boto3

        # Create a session so that credentials can be read from the [endpoint]
        # section in ~/.aws/credentials.
        # See https://boto3.readthedocs.io/en/latest/guide/configuration.html#guide-configuration
        self.session = boto3.Session(profile_name=endpoint)
        self.client = self.session.client('s3', endpoint_url='https://%s' % endpoint)

    def set_credentials(self,
                        endpoint: str,
                        access_key_id: str,
                        secret_access_key: str):
        """Set S3 credentials."""
        import boto3

        self.client = boto3.client('s3',
                                   endpoint_url=endpoint,
                                   aws_access_key_id=access_key_id,
                                   aws_secret_access_key=secret_access_key)

    def _create_file_transferer(self) -> transfer.FileTransferer:
        return S3Transferrer(self.client)


class S3Transferrer(transfer.FileTransferer):
    """Copies or moves files in source directory order."""

    class AbortUpload(Exception):
        """Raised from the upload callback to abort an upload."""

    def __init__(self, botoclient) -> None:
        super().__init__()
        self.client = botoclient

    def run(self) -> None:
        files_transferred = 0
        files_skipped = 0

        for src, dst, act in self.iter_queue():
            try:
                did_upload = self.upload_file(src, dst)
                files_transferred += did_upload
                files_skipped += not did_upload

                if act == transfer.Action.MOVE:
                    self.delete_file(src)
            except Exception:
                # We have to catch exceptions in a broad way, as this is running in
                # a separate thread, and exceptions won't otherwise be seen.
                log.exception('Error transferring %s to %s', src, dst)
                # Put the files to copy back into the queue, and abort. This allows
                # the main thread to inspect the queue and see which files were not
                # copied. The one we just failed (due to this exception) should also
                # be reported there.
                self.queue.put((src, dst, act))
                return

        if files_transferred:
            log.info('Transferred %d files', files_transferred)
        if files_skipped:
            log.info('Skipped %d files', files_skipped)

    def upload_file(self, src: pathlib.Path, dst: pathlib.Path) -> bool:
        """Upload a file to an S3 bucket.

        The first part of 'dst' is used as the bucket name, the remained as the
        path inside the bucket.

        :returns: True if the file was uploaded, False if it was skipped.
        """
        bucket = dst.parts[0]
        dst_path = pathlib.Path(*dst.parts[1:])
        md5 = compute_md5(src)
        key = str(dst_path)

        existing_md5, existing_size = self.get_metadata(bucket, key)
        if md5 == existing_md5 and src.stat().st_size == existing_size:
            log.debug('skipping %s, it already exists on the server with MD5 %s',
                      src, existing_md5)
            return False

        # TODO(Sybren): when queueing files inspect their size, and have a
        # callback that reports the total progress.
        log.info('Uploading %s', src)
        try:
            self.client.upload_file(str(src),
                                    Bucket=bucket,
                                    Key=key,
                                    Callback=self._upload_callback,
                                    ExtraArgs={'Metadata': {'md5': md5}})
        except self.AbortUpload:
            return False
        return True

    def _upload_callback(self, bytes_uploaded: int):
        if self.abort.is_set():
            log.warning('Interrupting ongoing upload')
            raise self.AbortUpload('interrupting ongoing upload')

    def delete_file(self, path: pathlib.Path):
        """Deletes a file, only logging a warning if deletion fails."""
        log.debug('Deleting %s, file has been uploaded', path)
        try:
            path.unlink()
        except IOError as ex:
            log.warning('Unable to delete %s: %s', path, ex)

    def get_metadata(self, bucket: str, key: str) -> typing.Tuple[str, int]:
        """Get MD5 sum and size on S3.

        :returns: the MD5 hexadecimal hash and the file size in bytes.
            If the file does not exist or has no known MD5 sum,
            returns ('', -1)
        """
        import botocore.exceptions

        try:
            info = self.client.head_object(Bucket=bucket, Key=key)
        except botocore.exceptions.ClientError as ex:
            error_code = ex.response.get('Error').get('Code', 'Unknown')
            # error_code already is a string, but this makes the code forward
            # compatible with a time where they use integer codes.
            if str(error_code) == '404':
                return '', -1
            raise ValueError('error response:' % ex.response) from None

        try:
            return info['Metadata']['md5'], info['ContentLength']
        except KeyError:
            return '', -1
