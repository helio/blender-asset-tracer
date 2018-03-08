import logging
import threading
import pathlib
import queue
import shutil
import typing

log = logging.getLogger(__name__)


class FileCopyError(IOError):
    """Raised when one or more files could not be copied."""

    def __init__(self, message, files_not_copied: typing.List[pathlib.Path]):
        super().__init__(message)
        self.files_not_copied = files_not_copied


class FileCopier(threading.Thread):
    """Copies files in directory order."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # For copying in a different process. By using a priority queue the files
        # are automatically sorted alphabetically, which means we go through all files
        # in a single directory at a time. This should be faster to copy than random
        # access. The order isn't guaranteed, though, as we're not waiting around for
        # all file paths to be known before copying starts.

        # maxsize=100 is just a guess as to a reasonable upper limit. When this limit
        # is reached, the main thread will simply block while waiting for this thread
        # to finish copying a file.
        self.file_copy_queue = queue.PriorityQueue(maxsize=100)
        self.file_copy_done = threading.Event()

    def queue(self, src: pathlib.Path, dst: pathlib.Path):
        """Queue a copy action from 'src' to 'dst'."""
        self.file_copy_queue.put((src, dst))

    def done_and_join(self):
        """Indicate all files have been queued, and wait until done."""

        self.file_copy_done.set()
        self.join()

        if not self.file_copy_queue.empty():
            # Flush the queue so that we can report which files weren't copied yet.
            files_remaining = []
            while not self.file_copy_queue.empty():
                src, dst = self.file_copy_queue.get_nowait()
                files_remaining.append(src)
            assert files_remaining
            raise FileCopyError("%d files couldn't be copied" % len(files_remaining),
                                files_remaining)

    def run(self):
        files_copied = 0
        files_skipped = 0

        while True:
            try:
                src, dst = self.file_copy_queue.get(timeout=0.1)
            except queue.Empty:
                if self.file_copy_done.is_set():
                    break
                continue

            try:
                if dst.exists():
                    st_src = src.stat()
                    st_dst = dst.stat()
                    if st_dst.st_size == st_src.st_size and st_dst.st_mtime >= st_src.st_mtime:
                        log.info('Skipping %s; already exists', src)
                        files_skipped += 1
                        continue

                log.info('Copying %s → %s', src, dst)
                dst.parent.mkdir(parents=True, exist_ok=True)
                # TODO(Sybren): when we target Py 3.6+, remove the str() calls.
                shutil.copy(str(src), str(dst))
                files_copied += 1
            except Exception:
                # We have to catch exceptions in a broad way, as this is running in
                # a separate thread, and exceptions won't otherwise be seen.
                log.exception('Error copying %s to %s', src, dst)
                # Put the files to copy back into the queue, and abort. This allows
                # the main thread to inspect the queue and see which files were not
                # copied. The one we just failed (due to this exception) should also
                # be reported there.
                self.file_copy_queue.put((src, dst))
                return

        if files_copied:
            log.info('Copied %d files', files_copied)
        if files_skipped:
            log.info('Skipped %d files', files_skipped)
