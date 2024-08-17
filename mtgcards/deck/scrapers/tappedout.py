"""

    mtgcards.deck.scrapers.tappedout.py
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Parse TappedOut decklist page.

    @author: z33k

"""
import logging

from mtgcards.const import Json
from mtgcards.deck import Deck, InvalidDeck
from mtgcards.deck.scrapers import DeckScraper
from mtgcards.deck.arena import ArenaParser
from mtgcards.utils import get_ago_date, extract_int
from mtgcards.utils.scrape import getsoup


_log = logging.getLogger(__name__)


class TappedoutScraper(DeckScraper):
    """Scraper of TappedOut decklist page.
    """
    def __init__(self, url: str, metadata: Json | None = None) -> None:
        super().__init__(url, metadata)
        self._soup = getsoup(url)
        self._scrape_metadata()
        self._deck = self._get_deck()

    @staticmethod
    def is_deck_url(url: str) -> bool:  # override
        return "tappedout.net/mtg-decks/" in url

    def _scrape_metadata(self) -> None:  # override
        fmt_tag = self._soup.select_one("a.btn.btn-success.btn-xs")
        fmt = fmt_tag.text.strip().removesuffix("*").lower()
        self._update_fmt(fmt)
        self._metadata["author"] = self._soup.select_one('a[href*="/users/"]').text.strip()
        deck_details_table = self._soup.find("table", id="deck-details")
        for row in deck_details_table.find_all("tr"):
            cols = row.find_all("td")
            if len(cols) != 2:
                continue
            name_col, value_col = cols
            if name_col.text.strip() == "Last updated":
                self._metadata["date"] = get_ago_date(value_col.text.strip())
            elif name_col.text.strip() == "Views":
                if views := value_col.text.strip():
                    self._metadata["views"] = extract_int(views)

    def _get_deck(self) -> Deck | None:  # override
        lines = self._soup.find("textarea", id="mtga-textarea").text.strip().splitlines()
        _, name_line, _, _, *lines = lines
        self._metadata["name"] = name_line.removeprefix("Name ")

        try:
            return ArenaParser(lines, self._metadata).deck
        except InvalidDeck as err:
            _log.warning(f"Scraping failed with: {err}")
            return None
