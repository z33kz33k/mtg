"""

    mtgcards.const.py
    ~~~~~~~~~~~~~~~~~
    Constants.

    @author: z33k

"""
from typing import Any, Callable, Dict, Tuple, TypeVar

# type annotation aliases
Json = Dict[str, Any]
T = TypeVar("T")
Method = Callable[[Any, Tuple[Any, ...]], Any]  # method with signature def methodname(self, *args)
Function = Callable[[Tuple[Any, ...]], Any]  # function with signature def funcname(*args)
MethodGeneric = Callable[[Any, Tuple[T, ...]], T]
FunctionGeneric = Callable[[Tuple[T, ...]], T]

DATE_FORMAT = "%Y-%m-%d %H:%M"
DATE_FORMAT_WITH_COMMA = "%Y-%m-%d, %H:%M"
TIMESTAMP_FORMAT = "%Y%m%d_%H%M_%f"

INPUTDIR, OUTPUTDIR = "input", "output"

