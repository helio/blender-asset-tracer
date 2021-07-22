import threading
import time
import typing
import unittest
from pathlib import Path
from unittest import mock

from blender_asset_tracer.pack import progress


class ThreadedProgressTest(unittest.TestCase):
    def test_threaded_progress(self):
        cb = mock.Mock(progress.Callback)
        tscb = progress.ThreadSafeCallback(typing.cast(progress.Callback, cb))

        # Flushing an empty queue should be fast.
        before = time.time()
        tscb.flush()
        duration = time.time() - before
        self.assertLess(duration, 1)

        def thread():
            tscb.pack_start()
            tscb.pack_done(Path("one"), {Path("two"), Path("three")})
            tscb.trace_asset(Path("four"))
            tscb.transfer_file(Path("five"), Path("six"))
            tscb.transfer_file_skipped(Path("seven"), Path("eight"))
            tscb.transfer_progress(327, 47)
            tscb.missing_file(Path("nine"))

        t = threading.Thread(target=thread)
        t.start()
        t.join(timeout=3)
        tscb.flush(timeout=3)

        cb.pack_start.assert_called_with()
        cb.pack_done.assert_called_with(Path("one"), {Path("two"), Path("three")})
        cb.trace_asset.assert_called_with(Path("four"))
        cb.transfer_file.assert_called_with(Path("five"), Path("six"))
        cb.transfer_file_skipped.assert_called_with(Path("seven"), Path("eight"))
        cb.transfer_progress.assert_called_with(327, 47)
        cb.missing_file.assert_called_with(Path("nine"))
