import enum
import logging
import threading
import pathlib
import queue
import shutil
import typing

log = logging.getLogger(__name__)


class FileCopyError(IOError):
    """Raised when one or more files could not be transferred."""

    def __init__(self, message, files_remaining: typing.List[pathlib.Path]) -> None:
        super().__init__(message)
        self.files_remaining = files_remaining


class Action(enum.Enum):
    COPY = 1
    MOVE = 2


class FileCopier(threading.Thread):
    """Copies or moves files in source directory order."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

        # For copying in a different process. By using a priority queue the files
        # are automatically sorted alphabetically, which means we go through all files
        # in a single directory at a time. This should be faster to copy than random
        # access. The order isn't guaranteed, though, as we're not waiting around for
        # all file paths to be known before copying starts.

        # maxsize=100 is just a guess as to a reasonable upper limit. When this limit
        # is reached, the main thread will simply block while waiting for this thread
        # to finish copying a file.
        self.queue = queue.PriorityQueue(maxsize=100) \
            # type: queue.PriorityQueue[typing.Tuple[pathlib.Path, pathlib.Path, Action]]
        self.done = threading.Event()

    def queue_copy(self, src: pathlib.Path, dst: pathlib.Path):
        """Queue a copy action from 'src' to 'dst'."""
        self.queue.put((src, dst, Action.COPY))

    def queue_move(self, src: pathlib.Path, dst: pathlib.Path):
        """Queue a move action from 'src' to 'dst'."""
        self.queue.put((src, dst, Action.MOVE))

    def done_and_join(self):
        """Indicate all files have been queued, and wait until done."""

        self.done.set()
        self.join()

        if not self.queue.empty():
            # Flush the queue so that we can report which files weren't copied yet.
            files_remaining = []
            while not self.queue.empty():
                src, dst = self.queue.get_nowait()
                files_remaining.append(src)
            assert files_remaining
            raise FileCopyError("%d files couldn't be transferred" % len(files_remaining),
                                files_remaining)

    def run(self):
        files_transferred = 0
        files_skipped = 0

        transfer_funcs = {
            Action.COPY: shutil.copy,
            Action.MOVE: shutil.move,
        }

        while True:
            try:
                src, dst, act = self.queue.get(timeout=0.1)
            except queue.Empty:
                if self.done.is_set():
                    break
                continue

            try:
                if dst.exists():
                    st_src = src.stat()
                    st_dst = dst.stat()
                    if st_dst.st_size == st_src.st_size and st_dst.st_mtime >= st_src.st_mtime:
                        log.info('SKIP %s; already exists', src)
                        if act == Action.MOVE:
                            log.debug('Deleting %s', src)
                            src.unlink()
                        files_skipped += 1
                        continue

                log.info('%s %s → %s', act.name, src, dst)
                dst.parent.mkdir(parents=True, exist_ok=True)

                # TODO(Sybren): when we target Py 3.6+, remove the str() calls.
                transfer = transfer_funcs[act]
                transfer(str(src), str(dst))

                files_transferred += 1
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
