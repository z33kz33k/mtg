"""

    mtg.utils.json
    ~~~~~~~~~~~~~~
    Utilities for JSON handling.

    @author: z33k

"""
import contextlib
import json
from collections import OrderedDict
from datetime import date, datetime
from typing import Any, Callable, Generator, Iterator, Self

from mtg import Json, READABLE_TIMESTAMP_FORMAT


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


def recursive_sort(obj: Json) -> Json:
    """Recursively sort any dicts contained in ``obj`` (by their keys).
    """
    if isinstance(obj, dict):
        return OrderedDict(
            (k, recursive_sort(v))
            for k, v in sorted(obj.items())
        )
    elif isinstance(obj, list):
        return [recursive_sort(x) for x in obj]
    return obj


def to_json(data: Json, sort_dictionaries=True) -> str:
    data = recursive_sort(data) if sort_dictionaries else data
    return json.dumps(data, indent=4, ensure_ascii=False, default=serialize_dates)


def from_json(json_text: str) -> Json:
    return json.loads(json_text, object_hook=deserialize_dates)


class Node:
    """A tree-building wrapper on dict/list deserialized from JSON.
    """
    @property
    def parents(self) -> tuple[Self, ...]:
        return self._parents

    @property
    def parent(self) -> Self | None:
        if not self.parents:
            return None
        return self.parents[0]

    @property
    def key(self) -> str | int:
        return self._key

    @property
    def data(self) -> Json:
        return self._data

    @property
    def children(self) -> tuple[Self, ...]:
        return self._children

    @property
    def name(self) -> str:
        if isinstance(self.key, str):
            name = f"[{self.key!r}]"
        elif isinstance(self.key, int):
            name = f"[{self.key}]"
        else:
            name = "/"
        return name

    @property
    def path(self) -> str:
        return self.build_path(*self.parents[::-1], self)

    @property
    def is_leaf(self) -> bool:
        return not self.children

    @property
    def is_root(self) -> bool:
        return not self.parents

    @property
    def next_sibling(self) -> Self | None:
        if self.is_root:
            return None
        try:
            return self.parent.children[self.parent.children.index(self) + 1]
        except IndexError:
            return None

    @property
    def previous_sibling(self) -> Self | None:
        if self.is_root:
            return None
        try:
            return self.parent.children[self.parent.children.index(self) - 1]
        except IndexError:
            return None

    def __init__(self, data: Json, *parents: Self, key: str | int | None = None) -> None:
        self._data, self._parents, self._key = data, parents, key
        self._children = self._get_children()

    def _get_children(self) -> tuple[Self, ...]:
        if isinstance(self.data, dict):
            return tuple(Node(d, self, *self.parents, key=k) for k, d in self.data.items())
        if isinstance(self.data, list):
            return tuple(Node(d, self, *self.parents, key=i) for i, d in enumerate(self.data))
        return ()

    def __len__(self) -> int:
        return len(self.children)

    def __str__(self) -> str:
        return self.name

    # NOTE: nodes are unique and hashable as long as only their 'path' is considered
    def __eq__(self, other: Self) -> bool:
        if isinstance(other, Node):
            return self.path == other.path
        return False

    def __hash__(self) -> int:
        return hash(self.path)

    def __iter__(self) -> Iterator[Self]:
        return iter(self.children)

    def iter(self) -> Iterator[Self]:
        """Yield all descendants of this node.
        """
        for descendant in self.find_all():
            yield descendant

    @classmethod
    def build_path(cls, *nodes: Self) -> str:
        return "".join(str(node) for node in nodes)

    # recursive
    def find_all(
            self,
            predicate: Callable[[Self], bool] = lambda _: True) -> Generator[Self, None, None]:
        """Traverse the tree from this node downwards and yield all nodes that satisfy
        ``predicate`` along the way. If no predicate is provided, all sub-nodes are yielded.

        Args:
            predicate: function that evaluates the traversed tree node to a boolean value

        Returns:
            a generator of all tree nodes that satisfy the predicate
        """
        for child in self.children:
            if predicate(child):
                yield child
        for child in self.children:
            yield from child.find_all(predicate)

    def find(self, predicate: Callable[[Self], bool]) -> Self | None:
        """Find the first node within subtree that satisfies ``predicate`` or None.

        Args:
            predicate: function that evaluates the traversed tree node to a boolean value

        Returns:
            tree node or None if it cannot be found
        """
        return next(self.find_all(predicate), None)

    def find_by_path(self, path: str, strict=False) -> Self | None:
        """Find the first node within subtree by its structural path.

        Args:
            path: structural path to test
            strict: if True, only a full match is enough, else a partial one is OK
        """
        if strict:
            return self.find(lambda n: n.path == path)
        return self.find(lambda n: path in n.path)

    @property
    def text_nodes(self) -> Generator[Self, None, None]:
        return self.find_all(lambda n: isinstance(n.data, str))
