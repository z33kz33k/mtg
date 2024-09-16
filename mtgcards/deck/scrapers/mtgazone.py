"""

    mtgcards.deck.scrapers.mtgazone.py
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Scrape MTG Arena Zone decklists.

    @author: z33k

"""
import logging
from datetime import datetime

from bs4 import Tag

from mtgcards import Json
from mtgcards.deck import Deck, InvalidDeck, Mode
from mtgcards.deck.scrapers import DeckScraper
from mtgcards.scryfall import Card, ARENA_FORMATS
from mtgcards.utils import extract_int, from_iterable, timed
from mtgcards.utils.scrape import ScrapingError, getsoup

_log = logging.getLogger(__name__)


# alternative approach would be to scrape:
# self._soup.find("input", {"type": "hidden", "name": "c"}).attrs["value"].split("||")
# but it has a downside of not having clear sideboard-maindeck separation
@DeckScraper.registered
class MtgaZoneScraper(DeckScraper):
    """Scraper of MTG Arena Zone decklist page.

    This scraper can be used both to scrape individual MTGAZone deck pages and to scrape
    decklist blocks that are aggregated on thematic (e.g. meta, post-rotation, guide) sites. In
    the latter case a deck block Tag object should be provided - a URL is not needed so an empty
    string should be passed instead.
    """
    def __init__(self, url: str, metadata: Json | None = None, deck_tag: Tag | None = None) -> None:
        super().__init__(url, metadata)
        self._deck_tag = deck_tag

    @staticmethod
    def is_deck_url(url: str) -> bool:  # override
        return "mtgazone.com/user-decks/" in url or "mtgazone.com/deck/" in url

    def _pre_parse(self) -> None:  # override
        self._soup = self._deck_tag or getsoup(self.url)
        if not self._soup:
            raise ScrapingError("Soup not available")

    def _parse_metadata(self) -> None:  # override
        name_author_tag = self._soup.find("div", class_="name-container")
        if not name_author_tag:
            raise ScrapingError(
                "Name tag not found. The deck you're trying to scrape has been most probably "
                "paywalled by MTGAZone")
        name_tag = name_author_tag.find("div", class_="name")
        name, author, event = name_tag.text.strip(), None, None
        if " by " in name:
            name, author = name.split(" by ")
        elif " – " in name:
            name, event = name.split(" – ")
        self._metadata["name"] = name
        author_tag = name_author_tag.find("div", class_="by")
        if not author_tag:
            raise ScrapingError(
                "Author tag not found. The deck you're trying to scrape has been most "
                "probably paywalled by MTGAZone")
        author = author_tag.text.strip().removeprefix("by ")
        self._metadata["author"] = author
        if event:
            self._metadata["event"] = event
        fmt_tag = self._soup.find("div", class_="format")
        if not fmt_tag:
            raise ScrapingError(
                "Format tag not found. The deck you're trying to scrape has been most probably "
                "paywalled by MTGAZone")
        fmt = fmt_tag.text.strip().lower()
        self._update_fmt(fmt)
        if time_tag := self._soup.find("time", class_="ct-meta-element-date"):
            self._metadata["date"] = datetime.fromisoformat(time_tag.attrs["datetime"]).date()

    @classmethod
    def _to_playset(cls, card_tag) -> list[Card]:
        quantity = int(card_tag.attrs["data-quantity"])
        a_tag = card_tag.find("a")
        name = a_tag.text.strip()
        *_, scryfall_id = a_tag.attrs["data-cimg"].split("/")
        scryfall_id, *_ = scryfall_id.split(".jpg")
        return cls.get_playset(cls.find_card(name, scryfall_id=scryfall_id), quantity)

    def _process_decklist(self, decklist_tag: Tag) -> list[Card]:
        decklist = []
        card_tags = decklist_tag.find_all("div", class_="card")
        for card_tag in card_tags:
            decklist.extend(self._to_playset(card_tag))
        return decklist

    def _parse_deck(self) -> None:  # override
        if commander_tag := self._soup.select_one("div.decklist.short.commander"):
            for card in self._process_decklist(commander_tag):
                self._set_commander(card)

        if companion_tag := self._soup.select_one("div.decklist.short.companion"):
            self._companion = self._process_decklist(companion_tag)[0]

        main_tag = self._soup.select_one("div.decklist.main")
        self._maindeck = self._process_decklist(main_tag)

        if sideboard_tags := self._soup.select("div.decklist.sideboard"):
            try:
                sideboard_tag = sideboard_tags[1]
                self._sideboard = self._process_decklist(sideboard_tag)
            except IndexError:
                pass


def _parse_tiers(table: Tag) -> dict[str, int]:
    tiers = {}
    for row in table.find_all("tr"):
        tier_col, deck_col = row.find_all("td")
        tier = extract_int(tier_col.find("strong").text)
        deck = deck_col.find("a").text.strip()
        tiers[deck] = tier
    return tiers


def _parse_meta_deck(deck_tag: Tag, decks2tiers: dict[str, int], deck_place: int) -> Deck:
    deck = MtgaZoneScraper("", deck_tag=deck_tag).scrape(suppress_invalid_deck=False)
    meta = {
        "meta": {
            "place": deck_place
        }
    }
    tier = decks2tiers.get(deck.name)
    if tier is None:
        deck_name = from_iterable(decks2tiers, lambda d: deck.name in d)
        if deck_name:
            tier = decks2tiers[deck_name]
    if tier:
        meta["meta"]["tier"] = tier
    deck.update_metadata(meta=meta["meta"])
    return deck


@timed("scraping meta decks")
def scrape_meta(fmt="standard", bo3=True) -> list[Deck]:
    formats = {fmt for fmt in ARENA_FORMATS if fmt not in {"brawl", "standardbrawl"}}
    formats = sorted({*formats, "pioneer"})
    fmt = fmt.lower()
    if fmt not in formats:
        raise ValueError(f"Invalid format: {fmt!r}. Can be only one of: {formats}")

    mode = "-bo3" if bo3 else "-bo1"
    if fmt == "pioneer":
        mode = ""
    url = f"https://mtgazone.com/{fmt}{mode}-metagame-tier-list/"

    soup = getsoup(url)
    if not soup:
        raise ScrapingError("Page not available")
    time_tag = soup.find("time", class_="ct-meta-element-date")
    deck_date = datetime.fromisoformat(time_tag.attrs["datetime"]).date()
    tier_table = soup.find("figure", class_="wp-block-table")
    table_body = tier_table.find("tbody")
    decks2tiers = _parse_tiers(table_body)

    decks = []
    for i, deck_tag in enumerate(soup.find_all("div", class_="deck-block"), start=1):
        deck = _parse_meta_deck(deck_tag, decks2tiers, i)
        deck.update_metadata(date=deck_date)
        deck.update_metadata(mode=mode[1:].title() if mode else Mode.BO3.value)
        decks.append(deck)

    return decks
