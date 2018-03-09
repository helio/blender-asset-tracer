import logging
import threading
import shutil

from . import transfer

log = logging.getLogger(__name__)


class FileCopier(threading.Thread, transfer.FileTransferer):
    """Copies or moves files in source directory order."""

    def __init__(self) -> None:
        # Stupid Thread.__init__ doesn't call super().__init__(),
        # so it doesn't get chained to transfer.FileTransferer.__init__().
        # However, I want to have Thread as first subclass so that its
        # start() and join() methods Just Work™.
        threading.Thread.__init__(self)
        transfer.FileTransferer.__init__(self)

    def run(self) -> None:
        files_transferred = 0
        files_skipped = 0

        transfer_funcs = {
            transfer.Action.COPY: shutil.copy,
            transfer.Action.MOVE: shutil.move,
        }

        for src, dst, act in self.iter_queue():
            try:
                if dst.exists():
                    st_src = src.stat()
                    st_dst = dst.stat()
                    if st_dst.st_size == st_src.st_size and st_dst.st_mtime >= st_src.st_mtime:
                        log.info('SKIP %s; already exists', src)
                        if act == transfer.Action.MOVE:
                            log.debug('Deleting %s', src)
                            src.unlink()
                        files_skipped += 1
                        continue

                log.info('%s %s → %s', act.name, src, dst)
                dst.parent.mkdir(parents=True, exist_ok=True)

                # TODO(Sybren): when we target Py 3.6+, remove the str() calls.
                tfunc = transfer_funcs[act]
                tfunc(str(src), str(dst))  # type: ignore

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
                break

        if files_transferred:
            log.info('Transferred %d files', files_transferred)
        if files_skipped:
            log.info('Skipped %d files', files_skipped)
