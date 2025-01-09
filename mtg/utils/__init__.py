"""

    mtg.utils.__init__.py
    ~~~~~~~~~~~~~~~~~~~~~
    Utilities.

    @author: z33k

"""
import contextlib
import hashlib
import itertools
import logging
import re
from collections import Counter as PyCounter
from datetime import datetime
from functools import wraps
from typing import Any, Callable, Iterable, Optional, Protocol, Sequence, Type
from datetime import date, timedelta

import dateutil.parser
from dateutil.relativedelta import relativedelta
from contexttimer import Timer
from lingua import Language, LanguageDetectorBuilder

from mtg import FILENAME_TIMESTAMP_FORMAT, READABLE_TIMESTAMP_FORMAT, T
from mtg.utils.check_type import type_checker, uniform_type_checker

_log = logging.getLogger(__name__)


def seconds2readable(seconds: float) -> str:
    seconds = round(seconds)
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    return f"{hours}h:{minutes:02}m:{seconds:02}s"


def timed(operation="", precision=3) -> Callable:
    """Add time measurement to the decorated operation.

    Args:
        operation: name of the time-measured operation (default is function's name)
        precision: precision of the time measurement in seconds (decides output text formatting)

    Returns:
        the decorated function
    """
    if precision < 0:
        precision = 0

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            with Timer() as t:
                result = func(*args, **kwargs)
            activity = operation or f"'{func.__name__}()'"
            time = seconds2readable(t.elapsed)
            if not precision:
                _log.info(f"Completed {activity} in {time}")
            elif precision == 1:
                _log.info(f"Completed {activity} in {t.elapsed:.{precision}f} "
                          f"second(s) ({time})")
            else:
                _log.info(f"Completed {activity} in {t.elapsed:.{precision}f} "
                          f"second(s)")
            return result
        return wrapper
    return decorator


def getrepr(class_: Type, *name_value_pairs: tuple[str, Any]) -> str:
    """Return ``__repr__`` string format: 'ClassName(name=value, ..., name_n=value_n)'

    Args:
        class_: class to get repr for
        name_value_pairs: variable number of (name, value) tuples
    """
    reprs = [f"{name}={value!r}" for name, value in name_value_pairs]
    return f"{class_.__name__}({', '.join(reprs)})"


@type_checker(str)
def extract_float(text: str) -> float:
    """Extract floating point number from text.
    """
    num = "".join([char for char in text if char.isdigit() or char in ",."])
    if not num:
        raise ParsingError(f"No digits or decimal point in text: {text!r}")
    return float(num.replace(",", "."))


@type_checker(str)
def extract_int(text: str) -> int:
    """Extract an integer from text.
    """
    num = "".join([char for char in text if char.isdigit()])
    if not num:
        raise ParsingError(f"No digits in text: {text!r}")
    return int(num)


@type_checker(str)
def get_date_from_ago_text(ago_text: str) -> date | None:
    """Parse 'ago' text (e.g. '2 days ago') into a Date object.
    """
    if not ago_text:
        return None
    dt = date.today()
    if "yesterday" in ago_text:
        return dt - timedelta(days=1)
    ago_text = ago_text.removesuffix(" ago")
    amount, time = ago_text.split()
    amount = 1 if amount in ("a", "an") else int(amount)
    if time in ("days", "day"):
        return dt - timedelta(days=amount)
    elif time in ("months", "month"):
        return dt - relativedelta(months=amount)
    elif time in ("years", "year"):
        return date(dt.year - amount, dt.month, dt.day)
    return None


@type_checker(str)
def get_date_from_french_ago_text(ago_text: str) -> date | None:
    """Parse French 'ago' text (e.g. '3 jours par') into a Date object.

    This aligns with Magic-Ville decklist pages.
    """
    if not ago_text:
        return None
    dt = date.today()
    if "hier" in ago_text:
        return dt - timedelta(days=1)
    if ":" in ago_text:
        return dt
    ago_text = ago_text.removesuffix(" par")
    amount, time = ago_text.split()
    amount = 1 if amount == "a" else int(amount)
    if time in ("jour", "jours"):
        return dt - timedelta(days=amount)
    elif time in ("semaine", "semaines", "sem."):
        return dt - relativedelta(weeks=amount)
    elif time == "mois":
        return dt - relativedelta(months=amount)
    elif time in ("années", "année"):
        return date(dt.year - amount, dt.month, dt.day)
    return None


@type_checker(str)
def get_date_from_month_text(month_text: str) -> date | None:
    """Parse 'month' text (e.g. 'June 27th') into a Date object.

    Month text may or may not include a valid year, e.g. 'June 27th 2021' or 'June 27th'. In case
    it's missing a current year is assumed.
    """
    current_year = datetime.now().year
    # clean the input string by removing ordinal suffixes
    cleaned_month_text = month_text.replace(
        'st', '').replace('nd', '').replace('rd', '').replace('th', '')

    parsed_date = dateutil.parser.parse(
        cleaned_month_text, default=datetime(current_year, 1, 1))
    return parsed_date.date()


@type_checker(str, none_allowed=True)
def getfloat(string: str | None) -> float | None:
    """Interpret string as floating point number or, if not possible, return None.
    """
    if not string:
        return None
    try:
        return extract_float(string)
    except ValueError:
        return None


@type_checker(str, none_allowed=True)
def getint(string: str | None) -> int | None:
    """Interpret string as integer or, if not possible, return None.
    """
    if not string:
        return None
    try:
        return extract_int(string)
    except ValueError:
        return None


@type_checker(str, none_allowed=True)
def getbool(string: str | None) -> bool | None:
    """Interpret string as boolean value or, if not possible, return None
    """
    if not string:
        return None
    if string.lower() == "false":
        return False
    elif string.lower() == "true":
        return True
    return None


@type_checker(str)
def camel_case_split(text: str) -> list[str]:
    """Do camel-case split on ``text``.

    Taken from:
        https://stackoverflow.com/a/58996565/4465708

    Args:
        text: text to be split

    Returns:
        a list of parts
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
    """Convert ``lst`` and any list it contains (no matter the nesting level) recursively to tuple.

    Taken from:
        https://stackoverflow.com/a/27050037/4465708
    """
    return tuple(totuple(i) if isinstance(i, list) else i for i in lst)


def tolist(tpl: tuple) -> list:
    """Convert ``tpl`` and any tuple it contains (no matter the nesting level) recursively to list.

    Taken from and made in reverse:
        https://stackoverflow.com/a/27050037/4465708
    """
    return list(tolist(i) if isinstance(i, tuple) else i for i in tpl)


def cleardir(obj: object) -> list[str]:
    """Return ``dir(obj)`` without extraneous fluff.
    """
    return [attr for attr in dir(obj) if not attr.startswith("_")]


def from_iterable(iterable: Iterable[T], predicate: Callable[[T], bool]) -> Optional[T]:
    """Return item from ``iterable`` based on ``predicate`` or ``None``, if it cannot be found.
    """
    return next((item for item in iterable if predicate(item)), None)


@uniform_type_checker(str)
def breadcrumbs(*crumbs: str) -> str:
    """Return a breadcrumb string based on ``crumbs`` supplied.

    Example:
        `/foo/bar/fiz/baz`
    """
    return "/" + "/".join(crumbs)


def timestamp(format_=FILENAME_TIMESTAMP_FORMAT) -> str:
    """Return timestamp string according to the datetime ``format_`` supplied.
    """
    return datetime.now().strftime(format_)


class ParsingError(ValueError):
    """Raised on unexpected states of parsed data.
    """


def serialize_dates(obj: Any) -> str:
    """Custom serializer for dates.

    To be used with json.dump() as ``default`` parameter.
    """
    if isinstance(obj, datetime):
        return obj.strftime(READABLE_TIMESTAMP_FORMAT)
    elif isinstance(obj, date):
        return obj.isoformat()
    raise TypeError(f"Type {type(obj)} not serializable")


def deserialize_dates(dct: dict) -> dict:
    """Custom deserializer for dates.

    To be used with json.load() as ``object_hook`` parameter.
    """
    for key, value in dct.items():
        if isinstance(value, str):
            # try to parse as datetime
            try:
                dct[key] = datetime.strptime(value, READABLE_TIMESTAMP_FORMAT)
            except ValueError:
                # if it fails, try to parse as date
                with contextlib.suppress(ValueError):
                    # leave it as a string if both parsing attempts fail
                    dct[key] = date.fromisoformat(value)
    return dct


def multiply_by_symbol(number: float, symbol: str) -> int:
    """Multiply ``number`` by ``symbol`` and return it.
    """
    if symbol in ('K', 'k'):
        return int(number * 1_000)
    elif symbol in ('M', 'm'):
        return int(number * 1_000_000)
    elif symbol in ('B', 'b'):
        return int(number * 1_000_000_000)
    elif symbol in ('T', 't'):
        return int(number * 1_000_000_000_000)
    if symbol:
        _log.warning(f"Unsupported symbol for multiplication: {symbol!r}")
    return int(number)


def sanitize_filename(text: str, replacement="_") -> str:  # perplexity
    """Sanitize a string to make it suitable for use as a filename.

    Args:
        text: The string to be sanitized.
        replacement: The character to replace invalid characters with (default is underscore).

    Returns:
        a sanitized string suitable for a filename.
    """
    # remove leading and trailing whitespace
    sanitized = text.strip()

    # replace invalid characters with the replacement character
    sanitized = re.sub(r'[<>:"/\\|?*]', replacement, sanitized)

    # replace any sequence of whitespace with a single underscore
    sanitized = re.sub(r'\s+', replacement, sanitized)

    # ensure the filename is not too long (most file systems have a limit of 255 characters)
    max_length = 255
    if len(sanitized) > max_length:
        sanitized = sanitized[:max_length]

    # ensure the filename does not end with a dot or space
    sanitized = sanitized.rstrip('. ')

    return sanitized


def sanitize_whitespace(text: str) -> str:
    """Replace whitespace sequences longer than one space in ``text`` with a single space.
    Replace non-breaking space with a regular one.
    """
    return re.sub(r'\s+', ' ', text).replace(' ', " ")


# list of languages Magic: The Gathering cards have been printed in
MTG_LANGS = {
    Language.ENGLISH,
    Language.FRENCH,
    Language.GERMAN,
    Language.ITALIAN,
    Language.SPANISH,
    Language.JAPANESE,
    Language.PORTUGUESE,
    Language.CHINESE,
    Language.RUSSIAN,
    Language.KOREAN,
}


def detect_mtg_lang(text: str) -> Language:
    """Detect language of ``text`` checking against those that Magic: The Gathering cards have
    been printed in.

    Args:
        text: MtG card text to detect the language of

    Raises:
        ValueError: if the detected language is not a Magic: The Gathering card language

    Returns:
        lingua.Language object
    """
    detector = LanguageDetectorBuilder.from_languages(*MTG_LANGS).build()
    detected_lang = detector.detect_language_of(text)
    if not detected_lang:
        raise ValueError("No language detected")
    if detected_lang in MTG_LANGS:
        return detected_lang
    raise ValueError(
        f"Detected language {detected_lang.name} is not a Magic: The Gathering card language")


def is_foreign(text: str) -> bool:
    try:
        lang = detect_mtg_lang(text)
    except ValueError:
        return False
    if lang.iso_code_639_1.name.lower() == "en":
        return True
    return False


class Counter(PyCounter):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._max_ord = len(str(len(self))) if self else 0
        self._max_name = max(len(name) for name in self) if self else 0
        self._max_count = len(str(max(count for count in self.values()))) if self else 0

    def print(self, title="") -> None:
        """Print this object in a neat table (with an optional title).
        """
        if not self:
            return

        if title:
            print(f" {title} ".center(
                self._max_ord + self._max_name + self._max_count + 16, "-"))
        for j, (name, count) in enumerate(self.most_common(), start=1):
            percent = f"{count * 100 / self.total():.2f} %"
            print(
                f"{j}.".ljust(self._max_ord + 1),
                name.ljust(self._max_name + 1),
                str(count).rjust(self._max_count + 1),
                f"({percent})".rjust(10),
            )
        print(
            f"".ljust(self._max_ord + 1),
            "TOTAL".ljust(self._max_name + 1),
            str(self.total()).rjust(self._max_count + 1),
            f"({100:.2f} %)".rjust(10),
        )

    def markdown(self, col_name="") -> str:
        """Turn this object into a Markdown table.

        Args:
            col_name: name of the main column
        """
        if not self:
            return ""

        markdown = []

        col_name = col_name or "Name"
        markdown.append(f"| No | {col_name} | Count | Percentage |")
        markdown.append("|:---|:-----|------:|-----------:|")

        total_count = self.total()

        for j, (name, count) in enumerate(self.most_common(), start=1):
            percent = f"{count * 100 / total_count:.2f} %"
            markdown.append(
                f"| {j:<{self._max_ord}} | {name:<{self._max_name}} "
                f"| {count:>{self._max_count}} | {percent:>10} |")

        markdown.append(
            f"|{'':<{self._max_ord}}| {'TOTAL':<{self._max_name}} "
            f"| {self.total():>{self._max_count}} | {100:.2f} %|")

        return "\n".join(markdown)


def digest(text: str) -> str:
    """Return SHA-256 hash of ``text``.
    """
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def getid(text: str) -> str:
    """Turn ``text`` into a unique identifier resembling Scryfall ones.
    """
    sha = digest(text)[:32]
    id_ = []
    for i, ch in enumerate(sha):
        if i == 8 or i == 12 or i == 16 or i == 20:
            id_.append("-")
        id_.append(ch)
    return "".join(id_)


class Comparable(Protocol):
    """Protocol for annotating comparable types.
    """
    def __lt__(self, other) -> bool:
        ...


def is_increasing(seq: Sequence[Comparable]) -> bool:
    if len(seq) < 2:
        return False
    return all(seq[i] > seq[i-1] for i, _ in enumerate(seq, start=1) if i < len(seq))


def find_longest_seqs(seq: list[int]) -> list[list[int]]:
    """Return a list of the longest increasing sequences in ``seq``.
    """
    if not is_increasing(seq):
        raise ValueError("Sequence must be increasing.")
    seqs = []
    for _, g in itertools.groupby(enumerate(seq), lambda pair: pair[1] - pair[0]):
        current_seq = [pair[1] for pair in g]
        seqs.append(current_seq)

    max_len = max(len(s) for s in seqs)
    return [group for group in seqs if len(group) == max_len]


def get_ordinal_suffix(num: int) -> str:
    """Return the ordinal suffix of ``num``.
    """
    return "th" if 11 <= num % 100 <= 13 else {1: "st", 2: "nd", 3: "rd"}.get(num % 10, "th")
