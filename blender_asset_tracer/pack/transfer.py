import abc
import enum
import pathlib
import queue
import threading
import typing


class FileTransferError(IOError):
    """Raised when one or more files could not be transferred."""

    def __init__(self, message, files_remaining: typing.List[pathlib.Path]) -> None:
        super().__init__(message)
        self.files_remaining = files_remaining


class Action(enum.Enum):
    COPY = 1
    MOVE = 2


QueueItem = typing.Tuple[pathlib.Path, pathlib.Path, Action]


class FileTransferer(metaclass=abc.ABCMeta):
    """Interface for file transfer classes."""

    class Empty(queue.Empty):
        """No more files to transfer, but more may be queued later."""

    class Done(queue.Empty):
        """No more files to transfer, work is done."""

    def __init__(self) -> None:
        super().__init__()

        # For copying in a different process. By using a priority queue the files
        # are automatically sorted alphabetically, which means we go through all files
        # in a single directory at a time. This should be faster to copy than random
        # access. The order isn't guaranteed, though, as we're not waiting around for
        # all file paths to be known before copying starts.

        # maxsize=100 is just a guess as to a reasonable upper limit. When this limit
        # is reached, the main thread will simply block while waiting for this thread
        # to finish copying a file.
        self.queue = queue.PriorityQueue(maxsize=100)  # type: queue.PriorityQueue[QueueItem]
        self.done = threading.Event()

    def queue_copy(self, src: pathlib.Path, dst: pathlib.Path):
        """Queue a copy action from 'src' to 'dst'."""
        self.queue.put((src, dst, Action.COPY))

    def queue_move(self, src: pathlib.Path, dst: pathlib.Path):
        """Queue a move action from 'src' to 'dst'."""
        self.queue.put((src, dst, Action.MOVE))

    def done_and_join(self) -> None:
        """Indicate all files have been queued, and wait until done.

        After this function has been called, the queue_xxx() methods should not
        be called any more.

        :raises FileTransferError: if there was an error transferring one or
            more files.
        """

        self.done.set()
        self.join()

        if not self.queue.empty():
            # Flush the queue so that we can report which files weren't copied yet.
            files_remaining = []
            while not self.queue.empty():
                src, dst, act = self.queue.get_nowait()
                files_remaining.append(src)
            assert files_remaining
            raise FileTransferError(
                "%d files couldn't be transferred" % len(files_remaining),
                files_remaining)

    def pop_queued(self) -> typing.Optional[QueueItem]:
        """Pops an item off the queue, waiting 0.1 sec if the queue is empty.

        :raises Done: when all files have been handled, and the work is done.
        :raises Empty: when the queue is empty, but more files may be queued
            in the future.
        """

        try:
            return self.queue.get(timeout=0.1)
        except queue.Empty:
            if self.done.is_set():
                raise self.Done()
            raise self.Empty()

    @abc.abstractmethod
    def start(self) -> None:
        """Starts the file transfer thread/process.

        This could spin up a separate thread to perform the actual file
        transfer. After start() is called, implementations should still accept
        calls to the queue_xxx() methods. In other words, this is not to be
        used as queue-and-then-start, but as start-and-then-queue.
        """

    @abc.abstractmethod
    def join(self, timeout=None):
        """Wait for the thread/process to stop."""
