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
# (c) 2018, Blender Foundation - Sybren A. Stüvel
import logging
import pathlib
import shutil
import typing

from . import transfer

log = logging.getLogger(__name__)


class FileCopier(transfer.FileTransferer):
    """Copies or moves files in source directory order."""

    def __init__(self):
        super().__init__()
        self.files_transferred = 0
        self.files_skipped = 0
        self.already_copied = set()

    def run(self) -> None:

        # (is_dir, action)
        transfer_funcs = {
            (False, transfer.Action.COPY): self.copyfile,
            (True, transfer.Action.COPY): self.copytree,
            (False, transfer.Action.MOVE): self.move,
            (True, transfer.Action.MOVE): self.move,
        }

        for src, dst, act in self.iter_queue():
            try:
                st_src = src.stat()  # must exist, or it wouldn't be queued.
                if dst.exists():
                    st_dst = dst.stat()
                    if st_dst.st_size == st_src.st_size and st_dst.st_mtime >= st_src.st_mtime:
                        log.info('SKIP %s; already exists', src)
                        if act == transfer.Action.MOVE:
                            log.debug('Deleting %s', src)
                            src.unlink()
                        self.files_skipped += 1
                        continue

                log.info('%s %s → %s', act.name, src, dst)
                dst.parent.mkdir(parents=True, exist_ok=True)

                tfunc = transfer_funcs[src.is_dir(), act]
                tfunc(src, dst)  # type: ignore
            except Exception:
                # We have to catch exceptions in a broad way, as this is running in
                # a separate thread, and exceptions won't otherwise be seen.
                log.exception('Error transferring %s to %s', src, dst)
                # Put the files to copy back into the queue, and abort. This allows
                # the main thread to inspect the queue and see which files were not
                # copied. The one we just failed (due to this exception) should also
                # be reported there.
                self.queue.put((src, dst, act), timeout=1.0)
                self._error.set()
                break

        if self.files_transferred:
            log.info('Transferred %d files', self.files_transferred)
        if self.files_skipped:
            log.info('Skipped %d files', self.files_skipped)

    def move(self, srcpath: pathlib.Path, dstpath: pathlib.Path):
        s_stat = srcpath.stat()
        shutil.move(str(srcpath), str(dstpath))

        self.files_transferred += 1
        self.report_transferred(s_stat.st_size)

    def copyfile(self, srcpath: pathlib.Path, dstpath: pathlib.Path):
        """Copy a file, skipping when it already exists."""

        if self._abort.is_set() or self._error.is_set():
            return

        if (srcpath, dstpath) in self.already_copied:
            log.debug('SKIP %s; already copied', srcpath)
            return

        s_stat = srcpath.stat()  # must exist, or it wouldn't be queued.
        if dstpath.exists():
            d_stat = dstpath.stat()
            if d_stat.st_size == s_stat.st_size and d_stat.st_mtime >= s_stat.st_mtime:
                log.info('SKIP %s; already exists', srcpath)
                self.progress_cb.transfer_file_skipped(srcpath, dstpath)
                self.files_skipped += 1
                return

        log.debug('Copying %s → %s', srcpath, dstpath)
        shutil.copy2(str(srcpath), str(dstpath))

        self.already_copied.add((srcpath, dstpath))
        self.files_transferred += 1

        self.report_transferred(s_stat.st_size)

    def copytree(self, src: pathlib.Path, dst: pathlib.Path,
                 symlinks=False, ignore_dangling_symlinks=False):
        """Recursively copy a directory tree.

        Copy of shutil.copytree() with some changes:

        - Using pathlib
        - The destination directory may already exist.
        - Existing files with the same file size are skipped.
        - Removed ability to ignore things.
        """

        if (src, dst) in self.already_copied:
            log.debug('SKIP %s; already copied', src)
            return

        dst.mkdir(parents=True, exist_ok=True)
        errors = []  # type: typing.List[typing.Tuple[pathlib.Path, pathlib.Path, str]]
        for srcpath in src.iterdir():
            dstpath = dst / srcpath.name
            try:
                if srcpath.is_symlink():
                    linkto = srcpath.resolve()
                    if symlinks:
                        # We can't just leave it to `copy_function` because legacy
                        # code with a custom `copy_function` may rely on copytree
                        # doing the right thing.
                        linkto.symlink_to(dstpath)
                        shutil.copystat(str(srcpath), str(dstpath), follow_symlinks=not symlinks)
                    else:
                        # ignore dangling symlink if the flag is on
                        if not linkto.exists() and ignore_dangling_symlinks:
                            continue
                        # otherwise let the copy occurs. copy2 will raise an error
                        if srcpath.is_dir():
                            self.copytree(srcpath, dstpath, symlinks)
                        else:
                            self.copyfile(srcpath, dstpath)
                elif srcpath.is_dir():
                    self.copytree(srcpath, dstpath, symlinks)
                else:
                    # Will raise a SpecialFileError for unsupported file types
                    self.copyfile(srcpath, dstpath)
            # catch the Error from the recursive copytree so that we can
            # continue with other files
            except shutil.Error as err:
                errors.extend(err.args[0])
            except OSError as why:
                errors.append((srcpath, dstpath, str(why)))
        try:
            shutil.copystat(str(src), str(dst))
        except OSError as why:
            # Copying file access times may fail on Windows
            if getattr(why, 'winerror', None) is None:
                errors.append((src, dst, str(why)))
        if errors:
            raise shutil.Error(errors)

        self.already_copied.add((src, dst))

        return dst
