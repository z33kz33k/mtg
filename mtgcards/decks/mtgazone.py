"""

    mtgcards.decks.mtgazone.py
    ~~~~~~~~~~~~~~~~~~~~~~~~~~
    Parse MTG Arena Zone decklist page.

    @author: z33k

"""
import logging

from bs4 import Tag

from mtgcards.const import Json
from mtgcards.decks import Deck, DeckScraper, InvalidDeckError, get_playset
from mtgcards.scryfall import Card, all_formats
from mtgcards.utils.scrape import getsoup


_log = logging.getLogger(__name__)


# TODO: meta-decks
class MtgazoneScraper(DeckScraper):
    """Scraper of MTG Arena Zone decklist page.
    """

    def __init__(self, url: str, metadata: Json | None = None, throttled=False) -> None:
        super().__init__(url, metadata)
        self._throttled = throttled
        self._soup = getsoup(url)
        self._update_metadata()
        self._deck = self._get_deck()

    @staticmethod
    def is_deck_url(url: str) -> bool:  # override
        return "mtgazone.com/user-decks/" in url or "mtgazone.com/deck/" in url

    def _update_metadata(self) -> None:  # override
        self._metadata["source"] = "mtgazone.com"
        name_author_tag = self._soup.find("div", class_="name-container")
        name_tag = name_author_tag.find("div", class_="name")
        name, author = name_tag.text.strip(), None
        if " by " in name:
            name, author = name.split(" by ")
        self._metadata["name"] = name
        if not self.author:
            if not author:
                author_tag = name_author_tag.find("div", class_="by")
                author = author_tag.text.strip().removeprefix("by ")
            self._metadata["author"] = author
        fmt_tag = self._soup.find("div", class_="format")
        fmt = fmt_tag.text.strip().lower()
        if fmt != self.fmt  and fmt in all_formats():
            if self.fmt:
                _log.warning(
                        f"Earlier specified format: {self.fmt!r} overwritten with a "
                        f"scraped one: {fmt!r}")
            self._metadata["format"] = fmt

    def _to_playset(self, card_tag) -> list[Card]:
        quantity = int(card_tag.attrs["data-quantity"])
        a_tag = card_tag.find("a")
        name = a_tag.text.strip()
        *_, scryfall_id = a_tag.attrs["data-cimg"].split("/")
        scryfall_id, *_ = scryfall_id.split(".jpg")
        if playset := self._get_playset_by_id(scryfall_id, quantity):
            return playset
        return get_playset(name, quantity, fmt=self.fmt)

    def _process_decklist(self, decklist_tag: Tag) -> list[Card]:
        decklist = []
        card_tags = decklist_tag.find_all("div", class_="card")
        for card_tag in card_tags:
            decklist.extend(self._to_playset(card_tag))
        return decklist

    def _get_deck(self) -> Deck | None:  # override
        mainboard, sideboard, commander, companion = [], [], None, None

        if commander_tag := self._soup.select_one("div.decklist.short.commander"):
            commander = self._process_decklist(commander_tag)[0]

        if companion_tag := self._soup.select_one("div.decklist.short.companion"):
            companion = self._process_decklist(companion_tag)[0]

        main_tag = self._soup.select_one("div.decklist.main")
        mainboard = self._process_decklist(main_tag)

        if sideboard_tags := self._soup.select("div.decklist.sideboard"):
            sideboard_tag = sideboard_tags[1]
            sideboard = self._process_decklist(sideboard_tag)

        try:
            return Deck(mainboard, sideboard, commander, companion, self._metadata)
        except InvalidDeckError as err:
            if self._throttled:
                raise
            _log.warning(f"Scraping failed with: {err}")
            return None
