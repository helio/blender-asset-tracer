import abc
import pathlib
import typing


class FileTransferError(IOError):
    """Raised when one or more files could not be transferred."""

    def __init__(self, message, files_remaining: typing.List[pathlib.Path]) -> None:
        super().__init__(message)
        self.files_remaining = files_remaining


class FileTransferer(metaclass=abc.ABCMeta):
    """Interface for file transfer classes."""

    @abc.abstractmethod
    def start(self):
        """Starts the file transfer thread/process.

        This could spin up a separate thread to perform the actual file
        transfer. After start() is called, implementations should still accept
        calls to the queue_xxx() methods. In other words, this is not to be
        used as queue-and-then-start, but as start-and-then-queue.
        """

    @abc.abstractmethod
    def queue_copy(self, src: pathlib.Path, dst: pathlib.Path) -> None:
        """Queue a copy action from 'src' to 'dst'."""

    @abc.abstractmethod
    def queue_move(self, src: pathlib.Path, dst: pathlib.Path) -> None:
        """Queue a move action from 'src' to 'dst'."""

    @abc.abstractmethod
    def done_and_join(self) -> None:
        """Indicate all files have been queued, and wait until done.

        After this function has been called, the queue_xxx() methods should not
        be called any more.

        :raises FileTransferError: if there was an error transferring one or
            more files.
        """
