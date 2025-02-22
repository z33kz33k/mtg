"""

    mtg.deck.scrapers.mtgjson.py
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Scrape MTGJSON decklists.

    @author: z33k

"""
import logging
from datetime import datetime
from typing import Generator, Literal

from tqdm import tqdm

from mtg import DECKS_DIR, FILENAME_TIMESTAMP_FORMAT, Json, PathLike
from mtg.deck import Deck, InvalidDeck
from mtg.deck.export import Exporter
from mtg.deck.scrapers import DeckScraper
from mtg.scryfall import Card
from mtg.utils import logging_disabled, timed
from mtg.utils.files import getdir
from mtg.utils.scrape import ScrapingError, getsoup, throttle, timed_request

_log = logging.getLogger(__name__)
URL = "https://mtgjson.com/api/v5/decks/"


@DeckScraper.registered
class MtgJsonDeckScraper(DeckScraper):
    """Scraper of MTGJSON decks page.
    """
    def __init__(self, url: str, metadata: Json | None = None) -> None:
        super().__init__(url, metadata)
        self._deck_data: Json | None = None

    @staticmethod
    def is_deck_url(url: str) -> bool:  # override
        return "mtgjson.com/api/v5/decks/" in url.lower() and url.lower().endswith(".json")

    def _pre_parse(self) -> None:  # override
        json_data = timed_request(self.url).json()
        if not json_data or not json_data.get("data"):
            raise ScrapingError("Data not available")
        self._metadata["date"] = datetime.fromisoformat(json_data["meta"]["date"]).date()
        self._metadata["version"] = json_data["meta"]["version"]
        self._deck_data = json_data["data"]

    def _parse_metadata(self) -> None:  # override
        self._metadata["name"] = self._deck_data["name"]
        self._metadata["release_date"] = datetime.fromisoformat(
            self._deck_data["releaseDate"]).date()
        self._metadata["type"] = self._deck_data["type"]

    def _parse_card_json(self, card_json: Json) -> list[Card]:
        qty = card_json["count"]
        name = card_json["name"]
        setcode = card_json["setCode"].lower()
        collector_number = card_json["number"]
        scryfall_id = card_json["identifiers"]["scryfallId"]
        card = self.find_card(
            name, set_and_collector_number=(setcode, collector_number), scryfall_id=scryfall_id)
        return self.get_playset(card, qty)

    def _parse_decklist(self) -> None:  # override
        for card_json in self._deck_data["commander"]:
            for card in self._parse_card_json(card_json):
                self._set_commander(card)
        for card_json in self._deck_data["mainBoard"]:
            self._maindeck += self._parse_card_json(card_json)
        for card_json in self._deck_data["sideBoard"]:
            self._sideboard += self._parse_card_json(card_json)


def _get_links():
    soup = getsoup(URL)
    if not soup:
        raise ScrapingError("API page not available")
    tbody = soup.find("tbody")
    link_tags = [t.find("a") for t in tbody.find_all("td", class_="link")]
    link_tags = [t for t in link_tags if t is not None]
    links = [
        f"{URL}{t['href']}" for t in link_tags
        if MtgJsonDeckScraper.is_deck_url(f"{URL}{t['href']}")]
    return links


@timed("scraping MTGJSON API deck page")
def scrape(*mtgjson_deck_links: str) -> Generator[Deck | None, None, None]:
    """Scrape MTGJSON API deck page for decks yielding one at a time.

    Decks not deemed Constructed-valid ones are ignored.
    """
    links = mtgjson_deck_links or _get_links()
    for i, link in enumerate(links, start=1):
        deck = None
        throttle(0.15)
        _log.info(f"Scraping deck {i}/{len(links)}: {link!r}...")
        try:
            deck = MtgJsonDeckScraper(link).scrape()
        except InvalidDeck as err:
            _log.warning(f"{link!r} yielded invalid deck: {err}")
            pass
        yield deck


def dump(
        dstdir: PathLike = "", fmt: Literal["arena", "forge", "json", "xmage"] = "xmage") -> None:
    """Export all Constructed decks available in MTGJSON API decks page to ```dstdir``` in the
    format provided.
    """
    timestamp = datetime.now().strftime(FILENAME_TIMESTAMP_FORMAT)
    dstdir = dstdir or DECKS_DIR / "mtgjson" / timestamp
    dstdir = getdir(dstdir)
    links = _get_links()
    with logging_disabled():
        for deck in tqdm(scrape(*links), total=len(links), desc="Exporting MTGJSON decks..."):
            if deck:
                exporter = Exporter(deck)
                try:
                    match fmt:
                        case "arena":
                            exporter.to_arena(dstdir)
                        case "forge":
                            exporter.to_forge(dstdir)
                        case "json":
                            exporter.to_json(dstdir)
                        case "xmage":
                            exporter.to_xmage(dstdir)
                except OSError as err:
                    if "File name too long" in str(err):
                        pass
                    else:
                        raise
