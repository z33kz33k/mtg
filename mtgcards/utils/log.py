"""

    mtgcards.utils.log.py
    ~~~~~~~~~~~~~~~~~~~~~

    Logging utilities.

"""
import logging
import sys
from pathlib import Path
from types import TracebackType
from typing import Any, Optional, Type

from mtgcards.utils import timestamp
from mtgcards.utils.validate import type_checker


LOGDIR_NAME = "logs"
STDOUT_FORMAT = "%(message)s"


# more or less copy of mtgcards.utils.files.getdir() too avoid circular imports
@type_checker(str)
def _getdir(dir_location: str) -> Path:
    """Return a Path object pointing at a directory according to string `dir_location` provided.

    If nothing exists at ``dir_location``, create a directory according to it (including any
    needed parents along the way). If ``dir_location`` points to an existing file,
    raise `ValueError`.
    """
    try:
        dir_ = Path(dir_location)
    except OSError:
        print(f"Cannot read the provided location: {dir_location}.")
        raise

    if not dir_.exists():
        print(f"Creating missing directory at: {dir_}...")
        dir_.mkdir(parents=True, exist_ok=True)
        return dir_
    else:
        if dir_.is_file():
            raise ValueError(f"Not a directory: {dir_}.")
    return dir_


@type_checker(str, str)
def _filepath(suffix: str, logdir: str) -> str:
    """Return logfile's string filepath.
    """
    filename = f"{timestamp()}_{suffix}.log" if suffix else f"{timestamp()}.log"
    return str(_getdir(logdir) / filename)


@type_checker(int, int)
def fileformat(module_name_length: int, lvl_name_length: int) -> str:
    """Return a logging format for logfile records based on supplied arguments.

    Args:
        module_name_length: char-length reserved for module's name
        lvl_name_length: char-length reserved for severity level
    """
    return f"%(asctime)s: %(name)-{module_name_length}s: %(levelname)-" \
           f"{lvl_name_length}s: %(message)s"


@type_checker(str, int, str)
def _filehandler(filepath: str, filelvl: int, file_format: str) -> logging.FileHandler:
    """Return a :class:`logging.FileHandler` object for the logfile.
    """
    filehandler = logging.FileHandler(Path(filepath), encoding="utf-8")
    filehandler.setLevel(filelvl)
    formatter = logging.Formatter(file_format)
    filehandler.setFormatter(formatter)
    return filehandler


@type_checker(int, stdoutformat=str)
def _streamhandler(stdoutlvl: int, stdoutformat=STDOUT_FORMAT) -> logging.StreamHandler:
    """Return a :class: `logging.StreamHandler` object for log records displayed in stdout.
    """
    streamhandler = logging.StreamHandler(stream=sys.stdout)
    streamhandler.setLevel(stdoutlvl)
    formatter = logging.Formatter(stdoutformat)
    streamhandler.setFormatter(formatter)
    return streamhandler


def rootlogger(module: str, output_dir: str, module_name_length=24, lvl_name_length=7,
               filelvl=logging.DEBUG, suffix="", stdoutlvl=logging.DEBUG) -> logging.Logger:
    """Return a root :class:`logging.Logger` object set-up according to supplied arguments.

    Note:
        Take care to run this function at the proper place to have logging behave correctly.
        ``module`` ought to be a root module for every other module that spawns a logger object with
        ``logging.getLogger()``. More on this in the official docs (paragraph starting with "The
        name is potentially..."):

        https://docs.python.org/3/library/logging.html

        That way the set-up is done only once, on the root and every other spawned logger is
        considered a root's descendant and all the root's settings are propagated downstream.

    Args:
        module: calling module's name
        output_dir: output directory location
        module_name_length: char-length reserved for module's name in the logfile records
        lvl_name_length:  char-length reserved for severity level in the logfile records
        filelvl: severity level of logfile records
        suffix: log filename's suffix
        stdoutlvl: severity level of standard output's records
    """
    logger = logging.getLogger(module)
    logger.setLevel(logging.DEBUG)
    logdir = _getdir(str(Path(output_dir) / LOGDIR_NAME))
    filepath = _filepath(suffix, str(logdir))
    format_ = fileformat(module_name_length, lvl_name_length)
    logger.addHandler(_filehandler(filepath, filelvl, format_))
    logger.addHandler(_streamhandler(stdoutlvl))
    return logger


class LoggingContext:
    """A context manager that logs messages on enter and exit.
    """
    def __init__(self, logger: logging.Logger, enter_msg: str | None = None,
                 exit_msg: str | None = None, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._log = logger
        self.enter_msg, self.exit_msg = enter_msg, exit_msg

    @property
    def enter_msg(self) -> str | None:
        return self.__enter_msg

    @enter_msg.setter
    @type_checker(str, is_method=True, none_allowed=True)
    def enter_msg(self, value: str | None) -> None:
        self.__enter_msg = value

    @property
    def exit_msg(self) -> str | None:
        return self.__exit_msg

    @exit_msg.setter
    @type_checker(str, is_method=True, none_allowed=True)
    def exit_msg(self, value: str | None) -> None:
        self.__exit_msg = value

    @property
    def log(self) -> logging.Logger:
        return self._log

    # CONTEXT MANAGER PROTOCOL
    def __enter__(self) -> "LoggingContext":
        """Enter context.
        """
        if self.enter_msg:
            self._log.info(self.enter_msg)
        return self

    # if __exit__() returns True, an exception that happened within 'with' is suppressed
    def __exit__(self, exc_type: Optional[Type[BaseException]],
                 exc_val: Optional[BaseException],
                 exc_tb: Optional[TracebackType]) -> bool:
        """Exit context.
        """
        if exc_type:
            self._log.error(f"{exc_type}: {exc_val}.")
        if self.exit_msg:
            self._log.info(self.exit_msg)
        return False
