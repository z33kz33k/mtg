"""

    mtgcards.const.py
    ~~~~~~~~~~~~~~~~~
    Constants.

    @author: z33k

"""
from typing import Any, Callable, TypeVar

from mtgcards import __appname__

# type annotation aliases
Json = dict[str, Any]
T = TypeVar("T")
Method = Callable[[Any, tuple[Any, ...]], Any]  # method with signature def methodname(self, *args)
Function = Callable[[tuple[Any, ...]], Any]  # function with signature def funcname(*args)
MethodGeneric = Callable[[Any, tuple[T, ...]], T]
FunctionGeneric = Callable[[tuple[T, ...]], T]

DATE_FORMAT = "%Y-%m-%d %H:%M"
DATE_FORMAT_WITH_COMMA = "%Y-%m-%d, %H:%M"
TIMESTAMP_FORMAT = "%Y%m%d_%H%M_%f"

INPUTDIR, OUTPUTDIR = "input", "output"
DATADIR = f"{__appname__}/data"
