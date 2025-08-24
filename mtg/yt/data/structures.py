"""

    mtg.yt.data.structures
    ~~~~~~~~~~~~~~~~~~~~~~
    Data structures.

    @author: z33k

"""
import json
from dataclasses import asdict, astuple, dataclass, fields
from datetime import date, datetime
from functools import lru_cache
from typing import Self

from mtg import Json
from mtg.deck import Deck
from mtg.deck.arena import ArenaParser
from mtg.gstate import DecklistsStateManager
from mtg.utils import Counter, breadcrumbs
from mtg.deck.scrapers.cardsrealm import get_source as cardsrealm_get_source
from mtg.deck.scrapers.edhrec import get_source as edhrec_get_source
from mtg.deck.scrapers.hareruya import get_source as hareruya_get_source
from mtg.deck.scrapers.melee import get_source as melee_get_source
from mtg.deck.scrapers.mtgarenapro import get_source as mtgarenapro_get_source
from mtg.deck.scrapers.scg import get_source as scg_get_source
from mtg.deck.scrapers.tcgplayer import get_source as tcgplayer_get_source
from mtg.utils.json import serialize_dates


ACTIVE_THRESHOLD = 14  # days (2 weeks)
DORMANT_THRESHOLD = 30 * 3  # days (ca 3 months)
ABANDONED_THRESHOLD = 30 * 12  # days (ca. 1 yr)
DECK_STALE_THRESHOLD = 50  # videos
VERY_DECK_STALE_THRESHOLD = 100  # videos
EXCESSIVELY_DECK_STALE_THRESHOLD = 150  # videos


def sanitize_source(src: str) -> str:
    src = src.removeprefix("www.")
    if new_src := cardsrealm_get_source(src):
        src = new_src
    elif new_src := edhrec_get_source(src):
        src = new_src
    elif new_src := hareruya_get_source(src):
        src = new_src
    elif new_src := melee_get_source(src):
        src = new_src
    elif new_src := mtgarenapro_get_source(src):
        src = new_src
    elif new_src := scg_get_source(src):
        src = new_src
    elif new_src := tcgplayer_get_source(src):
        src = new_src
    return src


@dataclass
class SerializedDeck:
    metadata: Json
    decklist_id: str
    decklist_extended_id: str

    @property
    def json(self) -> Json:
        return json.dumps(asdict(self), indent=4, ensure_ascii=False, default=serialize_dates)

    def __hash__(self) -> int:
        return hash(self.json)

    def __eq__(self, other: Self) -> bool:
        return isinstance(other, SerializedDeck) and self.json == other.json

    @lru_cache
    def deck(self, extended=True) -> Deck | None:
        manager = DecklistsStateManager()
        if not manager.is_loaded:
            manager.load()
        decklist = manager.retrieve(
            self.decklist_extended_id) if extended else manager.retrieve(self.decklist_id)
        if not decklist:
            return None
        return ArenaParser(decklist, self.metadata).parse()


# # TODO: formalize video data structure (#231)
@dataclass
class Video:
    id: str
    url: str
    author: str
    title: str
    description: str
    keywords: list[str]
    publish_time: datetime
    views: int
    sources: list[str]
    decks: list[SerializedDeck]
    # injected from Channel
    scrape_time: datetime | None = None

    @classmethod
    def from_dict(cls, data: Json) -> Self:
        field_names = {f.name for f in fields(cls)}
        data = {k: v for k, v in data.items() if k in field_names}
        data["decks"] = [SerializedDeck(**d) for d in data["decks"]]
        return cls(**data)


@dataclass
class Channel:
    id: str
    title: str | None
    description: str | None
    tags: list[str] | None
    subscribers: int
    scrape_time: datetime
    videos: list[dict]

    @property
    def decks(self) -> list[dict]:
        return [d for v in self.videos for d in v["decks"]]

    @property
    def sources(self) -> list[str]:
        return sorted({s for v in self.videos for s in v["sources"]})

    @property
    def deck_urls(self) -> set[str]:
        return {d["metadata"]["url"] for d in self.decks
                if d.get("metadata") and d["metadata"].get("url")}

    @property
    def deck_sources(self) -> Counter:
        return Counter(sanitize_source(d["metadata"]["source"]) for d in self.decks)

    @property
    def deck_formats(self) -> Counter:
        return Counter(d["metadata"]["format"] for d in self.decks if d["metadata"].get("format"))

    @property
    def staleness(self) -> int | None:
        return (date.today() - self.videos[0]["publish_time"].date()).days if self.videos else None

    @property
    def deck_staleness(self) -> int:
        """Return number of last scraped videos without a deck.
        """
        if not self.decks:
            return len(self.videos)
        video_ids = [v["id"] for v in self.videos]
        deck_ids = [v["id"] for v in self.videos if v["decks"]]
        return len(self.videos[:video_ids.index(deck_ids[0])])

    @property
    def span(self) -> int | None:
        if self.videos:
            return (self.videos[0]["publish_time"].date() - self.videos[-1]["publish_time"].date(
                )).days
        return None

    @property
    def posting_interval(self) -> float | None:
        return self.span / len(self.videos) if self.videos else None

    @property
    def total_views(self) -> int:
        return sum(v["views"] for v in self.videos)

    @property
    def subs_activity(self) -> float | None:
        """Return ratio of subscribers needed to generate one video view in inverted relation to 10
        subscribers, if available.

        The greater this number the more active the subscribers. 1 means 10 subscribers are
        needed to generate one video view. 2 means 5 subscribers are needed to generate one
        video view, 10 means 1 subscriber is needed one and so on.
        """
        avg_views = self.total_views / len(self.videos)
        return 10 / (self.subscribers / avg_views) if self.subscribers else None

    @property
    def decks_per_video(self) -> float | None:
        if not self.videos:
            return None
        return len(self.decks) / len(self.videos)

    @property
    def is_abandoned(self) -> bool:
        return self.staleness is not None and self.staleness > ABANDONED_THRESHOLD

    @property
    def is_dormant(self) -> bool:
        return (self.staleness is not None
                and ABANDONED_THRESHOLD >= self.staleness > DORMANT_THRESHOLD)

    @property
    def is_active(self) -> bool:
        return (self.staleness is not None
                and DORMANT_THRESHOLD >= self.staleness > ACTIVE_THRESHOLD)

    @property
    def is_fresh(self) -> bool:
        return not self.is_abandoned and not self.is_dormant and not self.is_active

    @property
    def is_deck_stale(self) -> bool:
        return VERY_DECK_STALE_THRESHOLD >= self.deck_staleness > DECK_STALE_THRESHOLD

    @property
    def is_very_deck_stale(self) -> bool:
        return EXCESSIVELY_DECK_STALE_THRESHOLD >= self.deck_staleness > VERY_DECK_STALE_THRESHOLD

    @property
    def is_excessively_deck_stale(self) -> bool:
        return self.deck_staleness > EXCESSIVELY_DECK_STALE_THRESHOLD

    @property
    def is_deck_fresh(self) -> bool:
        return not (self.is_deck_stale or self.is_very_deck_stale or self.is_excessively_deck_stale)

    @property
    def json(self) -> Json:
        return json.dumps(asdict(self), indent=4, ensure_ascii=False, default=serialize_dates)


@dataclass(frozen=True)
class DataPath:
    """Structural path to a channel/video/decklist in the channel data.
    """
    channel_id: str
    video_id: str | None = None
    decklist_id: str | None = None

    def __str__(self) -> str:
        return breadcrumbs(*[crumb for crumb in astuple(self) if crumb])

    @classmethod
    def from_path(cls, path: str) -> Self:
        parts = path.strip("/").split("/", maxsplit=2)
        return cls(*parts)
