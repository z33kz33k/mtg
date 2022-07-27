"""

    mtgcards.utils.py
    ~~~~~~~~~~~~~~~~~
    Utilities.

    @author: z33k

"""
from datetime import datetime
from typing import Callable, Iterable, List, Optional, Union

import requests
from contexttimer import Timer

from mtgcards.const import T, TIMESTAMP_FORMAT, Json
from mtgcards.utils.validate import uniform_type_checker, type_checker


def timed_request(url: str, postdata: Optional[Json] = None,
                  return_json=False) -> Union[List[Json], Json, str]:
    print(f"Retrieving data from: '{url}'...")
    with Timer() as t:
        if postdata:
            data = requests.post(url, json=postdata)
        else:
            data = requests.get(url)
    print(f"Request completed in {t.elapsed:.3f} seconds.")
    if return_json:
        return data.json()
    return data.text


def getrepr(classname: str, *reprs: str) -> str:
    """Return ``__repr__`` string for reprs of format: 'name=value'

    :param classname: name of the class to get repr for
    :param reprs: repr part strings
    :return: repr string
    """
    return f"{classname}({', '.join(reprs)})"


@type_checker(str)
def parse_bool_from_str(string: str) -> Optional[bool]:
    """Parse a boolean value or ``None`` from ``string``.
    """
    if not string:
        return None
    if string.lower() == "false":
        return False
    elif string.lower() == "true":
        return True
    return None


@type_checker(str)
def parse_float_from_str(string: str) -> Optional[float]:
    """Parse a floating point number or ``None`` from ``string``.
    """
    if not string:
        return None
    string = string.replace(",", ".") if "," in string else string
    try:
        result = float(string)
    except ValueError:
        return None
    return result


@type_checker(str)
def parse_int_from_str(string: str) -> Optional[int]:
    """Parse an integer or ``None`` from ``string``.
    """
    if not string:
        return None
    try:
        result = int(string)
    except ValueError:
        return None
    return result


@type_checker(str)
def camel_case_split(text: str) -> List[str]:
    """Do camel-case split on ``text``.

    Taken from:
        https://stackoverflow.com/a/58996565/4465708

    :param text: text to be split
    :return: a list of parts
    """
    bools = [char.isupper() for char in text]
    # mark change of case
    upper_chars_indices = [0]  # e.g.: [0, 8, 8, 17, 17, 25, 25, 28, 29]
    for (i, (first_char_is_upper, second_char_is_upper)) in enumerate(zip(bools, bools[1:])):
        if first_char_is_upper and not second_char_is_upper:  # "Cc"
            upper_chars_indices.append(i)
        elif not first_char_is_upper and second_char_is_upper:  # "cC"
            upper_chars_indices.append(i + 1)
    upper_chars_indices.append(len(text))
    # for "cCc", index of "C" will pop twice, have to filter that
    return [text[x:y] for x, y in zip(upper_chars_indices, upper_chars_indices[1:]) if x < y]


def totuple(lst: list) -> tuple:
    """Convert ``lst`` and any list it containes (no matter the nesting level) recursively to tuple.

    Taken from:
        https://stackoverflow.com/a/27050037/4465708
    """
    return tuple(totuple(i) if isinstance(i, list) else i for i in lst)


def tolist(tpl: tuple) -> list:
    """Convert ``tpl`` and any tuple it containes (no matter the nesting level) recursively to list.

    Taken from and maid in reverse:
        https://stackoverflow.com/a/27050037/4465708
    """
    return list(tolist(i) if isinstance(i, tuple) else i for i in tpl)


def cleardir(obj: object) -> List[str]:
    """Return ``dir(obj)`` without extraneous fluff.
    """
    return [attr for attr in dir(obj) if not attr.startswith("_")]


def from_iterable(iterable: Iterable[T], predicate: Callable[[T], bool]) -> Optional[T]:
    """Return item from ``iterable`` based on ``predicate`` or ``None``, if it cannout be found.
    """
    return next((item for item in iterable if predicate(item)), None)


@uniform_type_checker(str)
def breadcrumbs(*crumbs: str) -> str:
    """Return a breadcrumb string based on ``crumbs`` supplied.

    Example:
        `/foo/bar/fiz/baz`
    """
    return "/" + "/".join(crumbs)


def timestamp(format_=TIMESTAMP_FORMAT) -> str:
    """Return timestamp string according to the datetime ``format_`` supplied.
    """
    return datetime.now().strftime(format_)
