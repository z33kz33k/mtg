"""

    mtgcards.yt.py
    ~~~~~~~~~~~~~~
    Handle YouTube data.

    @author: z33k

"""
import itertools
import re
from collections import defaultdict, Counter
from enum import Enum, auto
from datetime import datetime
from decimal import Decimal
from typing import DefaultDict, List, Optional, Set, Tuple

import requests
from scrapetube import get_channel
from pytube import YouTube
from youtubesearchpython import Channel as YtspChannel

from mtgcards.const import Json
from mtgcards.scryfall import formats as scryfall_formats
from mtgcards.scryfall import format_cards, Card, Deck, find_by_name_narrowed_by_collector_number, \
    set_cards
from mtgcards.yt.arena import ArenaLine


class _ArenaParsing(Enum):
    """State machine for Arena lines parsing

    """
    IDLE = auto()
    MAINLIST = auto()
    COMMANDER = auto()
    SIDEBOARD = auto()

    @classmethod
    def shift_to_idle(cls, current_state: "_ArenaParsing") -> "_ArenaParsing":
        if current_state not in (_ArenaParsing.MAINLIST, _ArenaParsing.COMMANDER,
                                 _ArenaParsing.SIDEBOARD):
            raise RuntimeError(f"Invalid transition to IDLE from: {current_state.name}")
        return _ArenaParsing.IDLE

    @classmethod
    def shift_to_mainlist(cls, current_state: "_ArenaParsing") -> "_ArenaParsing":
        if current_state is not _ArenaParsing.IDLE:
            raise RuntimeError(f"Invalid transition to MAIN_LIST from: {current_state.name}")
        return _ArenaParsing.MAINLIST

    @classmethod
    def shift_to_commander(cls, current_state: "_ArenaParsing") -> "_ArenaParsing":
        if current_state is not _ArenaParsing.IDLE:
            raise RuntimeError(f"Invalid transition to COMMANDER from: {current_state.name}")
        return _ArenaParsing.COMMANDER

    @classmethod
    def shift_to_sideboard(cls, current_state: "_ArenaParsing") -> "_ArenaParsing":
        if current_state is not _ArenaParsing.IDLE:
            raise RuntimeError(f"Invalid transition to SIDEBOARD from: {current_state.name}")
        return _ArenaParsing.SIDEBOARD


class Video:
    """YouTube video showcasing a MtG deck with its most important metadata.
    """
    URL_TEMPLATE = "https://www.youtube.com/watch?v={}"

    # decklist hooks
    AETHERHUB_HOOK = "aetherhub.com/Deck/"
    GOLDFISH_HOOK = "mtggoldfish.com/deck/"
    MOXFIELD_HOOK = "moxfield.com/decks/"
    MTGAZONE_HOOK = "mtgazone.com/user-decks/"
    STREAMDECKER_HOOK = "streamdecker.com/deck/"
    TCGPLAYER_HOOK = "decks.tcgplayer.com/"
    UNTAPPED_HOOKS = {"mtga.untapped.gg", "/deck/"}

    SHORTENER_HOOKS = {"bit.ly/", "tinyurl.com/", "cutt.ly/", "rb.gy/", "shortcm.li/", "tiny.cc/",
                       "snip.ly/", "qti.ai/", "dub.sh/", "lyksoomu.com/", "zws.im/", "t.ly/"}

    formats = scryfall_formats()

    @property
    def id(self) -> str:
        return self._scrapetube_data["videoId"]

    @property
    def author(self) -> str:
        return self._pytube_data.author

    @property
    def channel_id(self) -> str:
        return self._pytube_data.channel_id

    @property
    def description(self) -> str:
        return self._pytube_data.description

    @property
    def keywords(self) -> List[str]:
        return self._pytube_data.keywords

    @property
    def published_date(self) -> datetime:
        return self._pytube_data.publish_date

    @property
    def title(self) -> str:
        return self._pytube_data.title

    @property
    def views(self) -> int:
        return self._pytube_data.views

    @property
    def _desc_lines(self) -> List[str]:
        return [line.strip() for line in self.description.split("\n")]

    @property
    def links(self) -> List[str]:
        return self._links

    @property
    def shortened_links(self) -> Set[str]:
        return {link for link in self.links if any(hook in link for hook in self.SHORTENER_HOOKS)}

    @property
    def format(self) -> str:
        return self._format

    @property
    def arena_lines(self) -> List[ArenaLine]:
        return self._arena_lines

    @property
    def arena_sideboard_lines(self) -> List[ArenaLine]:
        return self._arena_sideboard_lines

    @property
    def deck(self) -> Optional[Deck]:
        return self._deck

    def __init__(self, scrapetube_data: Json) -> None:
        self._scrapetube_data = scrapetube_data
        self._pytube_data = YouTube(self.URL_TEMPLATE.format(self.id))
        self._format_soup: DefaultDict[str, List[str]] = defaultdict(list)
        self._extract_formats(self.title)
        self._arena_parsing = _ArenaParsing.IDLE
        self._links, self._arena_lines, self._arena_sideboard_lines = self._parse_lines()
        self._format = self._get_format()
        self._format_cards = format_cards(self._format)
        self._deck = self._get_deck()

    def _extract_formats(self, line: str) -> None:
        formats = [word.lower() for word in line.strip().split() if word.lower() in self.formats]
        for fmt in formats:
            self._format_soup[fmt].append(fmt)

    def _get_format(self) -> str:
        # if format soup has been populated from title and description, take the most common item
        if self._format_soup:
            return Counter(itertools.chain(*self._format_soup.values())).most_common(1)[0][0]
        # if not, fall back to default
        return "standard"

    def _parse_lines(self
                     ) -> Tuple[List[str], List[ArenaLine], List[ArenaLine], Optional[ArenaLine]]:
        links, arena_lines, arena_sideboard_lines, commander_line = [], [], [], None
        for i, line in enumerate(self._desc_lines):
            self._extract_formats(line)
            url = exctract_url(line)
            if url:
                links.append(url)
            else:
                # Arena parsing
                if not line or line.isspace():
                    self._arena_parsing = _ArenaParsing.shift_to_idle(self._arena_parsing)
                elif line.startswith("Sideboard"):
                    self._arena_parsing = _ArenaParsing.shift_to_sideboard(self._arena_parsing)
                elif line.startswith("Commander"):
                    self._arena_parsing = _ArenaParsing.shift_to_commander(self._arena_parsing)
                else:
                    match = ArenaLine.PATTERN.match(line)
                    if match:
                        if self._arena_parsing is _ArenaParsing.IDLE:
                            self._arena_parsing = _ArenaParsing.shift_to_mainlist(
                                self._arena_parsing)

                        if self._arena_parsing is _ArenaParsing.SIDEBOARD:
                            arena_sideboard_lines.append(ArenaLine(line))
                        elif self._arena_parsing is _ArenaParsing.COMMANDER:
                            commander_line = ArenaLine(line)
                        elif self._arena_parsing is _ArenaParsing.MAINLIST:
                            arena_lines.append(ArenaLine(line))

        return links, arena_lines, arena_sideboard_lines, commander_line

    def _process_arena_line(self, arena_line: ArenaLine) -> List[Card]:
        if arena_line.is_extended:
            cards = set_cards(arena_line.set_code.lower())
            card = find_by_name_narrowed_by_collector_number(arena_line.name, cards)
            if card:
                return [card] * arena_line.quantity

        card = find_by_name_narrowed_by_collector_number(arena_line.name, self._format_cards)
        if card:
            return [card] * arena_line.quantity

        return []

    def _get_arena_deck(self, card_lines: List[ArenaLine],
                        sideboard_lines: List[ArenaLine]) -> Optional[Deck]:
        cards, sideboard = [], []
        for card_line in card_lines:
            processed = self._process_arena_line(card_line)
            if not processed:
                print(f"Card not found for main list: {card_line}")
                return None
            cards.extend(processed)
        for sideboard_line in sideboard_lines:
            processed = self._process_arena_line(sideboard_line)
            if not processed:
                print(f"Card not found for sideboard: {sideboard_line}")
                break
        return Deck(cards, sideboard)

    def _get_deck(self) -> Optional[Deck]:
        if self.arena_lines and sum(al.quantity for al in self.arena_lines) >= Deck.MIN_SIZE:
            return self._get_arena_deck(self.arena_lines, self.arena_sideboard_lines)
        # TODO: more
        return None


class Channel(list):
    """A list of videos showcasing a MtG deck with its most important metadata.
    """
    @property
    def url(self) -> str:
        return self._url

    @property
    def id(self) -> Optional[str]:
        return self._id

    @property
    def title(self) -> Optional[str]:
        return self._title

    @property
    def tags(self) -> Optional[List[str]]:
        return self._tags

    @property
    def subscribers(self) -> Optional[int]:
        return self._subscribers

    def __init__(self, url: str, limit=10) -> None:
        try:
            videos = [*get_channel(channel_url=url, limit=limit)]
        except OSError:
            raise ValueError(f"Invalid URL: {url!r}")
        super().__init__([Video(data) for data in videos])
        self._url = url
        self._id = self[0].channel_id if self else None
        self._ytsp_data = YtspChannel(self.id) if self._id else None
        self._title = self._ytsp_data.result["title"] if self._id else None
        self._tags = self._ytsp_data.result["tags"] if self._id else None
        self._subscribers = self._parse_subscribers() if self._id else None

    def _parse_subscribers(self) -> int:
        text = self._ytsp_data.result["subscribers"]["simpleText"]
        number = text.rstrip(" subscribers").rstrip("KM")
        subscribers = Decimal(number)
        if "K" in text:
            subscribers *= 1000
        elif "M" in text:
            subscribers *= 1_000_000
        return int(subscribers)


def unshorten(url: str) -> str:
    """Unshorten URL shortened by services like bit.ly, tinyurl.com etc.

    Pilfered from: https://stackoverflow.com/a/28918160/4465708
    """
    session = requests.Session()  # so connections are recycled
    resp = session.head(url, allow_redirects=True)
    return resp.url


def exctract_url(text: str, https=True) -> Optional[str]:
    """Extract (the firs occurance of) URL from ``text``.

    Pilfered from: https://stackoverflow.com/a/840110/4465708
    """
    pattern = r"(?P<url>https?://[^\s'\"]+)" if https else r"(?P<url>http?://[^\s'\"]+)"
    match = re.search(pattern, text)
    return match.group("url") if match else None
