"""

    mtgcards.decks.goldfish.py
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Parse MtGGoldfish decklists.

    @author: z33k

"""
import logging
from datetime import datetime

from bs4 import Tag

from mtgcards.const import Json
from mtgcards.decks import Deck, DeckScraper, InvalidDeck, Mode, ParsingState
from mtgcards.scryfall import Card, all_formats
from mtgcards.utils import ParsingError, extract_int, timed
from mtgcards.utils.scrape import ScrapingError, getsoup, http_requests_counted, throttled_soup

_log = logging.getLogger(__name__)


# alternative approach would be to scrape:
# self._soup.find("input", id="deck_input_deck").attrs["value"] which contains a decklist in
# Arena format (albeit with the need to .replace("sideboard", "Sideboard") or maybe some other
# safer means to achieve the same effect)
# yet another alternative approach would be to scrape:
# https://www.mtggoldfish.com/deck/arena_download/{DECK_ID} but this entails another request and
# parsing a DECK_ID from the first URL
class GoldfishScraper(DeckScraper):
    """Scraper of MtGGoldfish decklist page.
    """
    HEADERS = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Chrome/96.0.4664.113 Safari/537.36}",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,"
                  "image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9"
    }

    FMT_NAMES = {
        "penny dreadful": "penny",
        "pauper commander": "paupercommander",
        "standard brawl": "standardbrawl",
    }

    def __init__(self, url: str, metadata: Json | None = None, throttled=False) -> None:
        super().__init__(url, metadata)
        self._throttled = throttled
        self._soup = throttled_soup(
            url, headers=self.HEADERS) if self._throttled else getsoup(url, headers=self.HEADERS)
        self._scrape_metadata()
        self._deck = self._get_deck()

    @staticmethod
    def is_deck_url(url: str) -> bool:  # override
        return "www.mtggoldfish.com/deck/" in url or "www.mtggoldfish.com/archetype/" in url

    def _shift_to_commander(self) -> None:  # override
        if self._state not in (ParsingState.IDLE, ParsingState.COMPANION):
            raise ParsingError(f"Invalid transition to COMMANDER from: {self._state.name}")
        self._state = ParsingState.COMMANDER

    def _shift_to_companion(self) -> None:  # override
        if self._state not in (ParsingState.IDLE, ParsingState.COMMANDER):
            raise ParsingError(f"Invalid transition to COMPANION from: {self._state.name}")
        self._state = ParsingState.COMPANION

    def _shift_to_mainboard(self) -> None:  # override
        if self._state not in (ParsingState.IDLE, ParsingState.COMMANDER, ParsingState.COMPANION):
            raise ParsingError(f"Invalid transition to MAINBOARD from: {self._state.name}")
        self._state = ParsingState.MAINBOARD

    def _shift_to_sideboard(self) -> None:  # override
        if self._state is not ParsingState.MAINBOARD:
            raise ParsingError(f"Invalid transition to SIDEBOARD from: {self._state.name}")
        self._state = ParsingState.SIDEBOARD

    def _scrape_metadata(self) -> None:  # override
        title_tag = self._soup.find("h1", class_="title")
        self._metadata["name"], *_ = title_tag.text.strip().split("\n")
        if not self.author:
            author_tag = title_tag.find("span")
            if author_tag is not None:
                self._metadata["author"] = author_tag.text.strip().removeprefix("by ")
        info_tag = self._soup.find("p", class_="deck-container-information")
        lines = [l for l in info_tag.text.splitlines() if l]
        source_idx = None
        for i, line in enumerate(lines):
            if line.startswith("Format:"):
                fmt = line.removeprefix("Format:").strip().lower()
                if fmt in self.FMT_NAMES:
                    fmt = self.FMT_NAMES[fmt]
                self._update_fmt(fmt)
            elif line.startswith("Event:"):
                self._metadata["event"] = line.removeprefix("Event:").strip()
            elif line.startswith("Deck Source:"):
                source_idx = i + 1
            elif line.startswith("Deck Date:"):
                self._metadata["date"] = datetime.strptime(
                    line.removeprefix("Deck Date:").strip(), "%b %d, %Y").date()
        if source_idx is not None:
            self._metadata["original_source"] = lines[source_idx].strip()

    @classmethod
    def _to_playset(cls, row: Tag) -> list[Card]:
        quantity_tag = row.find(class_="text-right")
        if not quantity_tag:
            raise ScrapingError("Can't find quantity data in a row tag")
        quantity = extract_int(quantity_tag.text.strip())

        a_tag = row.find("a")
        if not a_tag:
            raise ScrapingError("Can't find name and set data a row tag")
        text = a_tag.attrs.get("data-card-id")
        if not text:
            raise ScrapingError("Can't find name and set data a row tag")
        if "[" not in text or "]" not in text:
            raise ScrapingError(f"No set data in: {text!r}")
        name, _ = text.split("[")
        name = name.strip()
        if "<" in name:
            name, *rest = name.split("<")
            name = name.strip()

        return cls.get_playset(cls.find_card(name), quantity)

    def _get_deck(self) -> Deck | None:  # override
        mainboard, sideboard, commander, companion = [], [], None, None
        table = self._soup.find("table", class_="deck-view-deck-table")
        rows = table.find_all("tr")
        headers = (
            "Creatures", "Planeswalkers", "Spells", "Battles", "Artifacts", "Enchantments", "Lands")
        for row in rows:
            if row.has_attr("class") and "deck-category-header" in row.attrs["class"]:
                if row.text.strip() == "Commander":
                    self._shift_to_commander()
                elif row.text.strip().startswith("Companion"):
                    self._shift_to_companion()
                elif any(h in row.text.strip() for h in headers
                         ) and self._state is not ParsingState.MAINBOARD:
                    self._shift_to_mainboard()
                elif "Sideboard" in row.text.strip():
                    self._shift_to_sideboard()
            else:
                cards = self._to_playset(row)
                if self._state is ParsingState.COMMANDER:
                    if cards:
                        commander = cards[0]
                elif self._state is ParsingState.COMPANION:
                    if cards:
                        companion = cards[0]
                elif self._state is ParsingState.MAINBOARD:
                    mainboard.extend(cards)
                elif self._state is ParsingState.SIDEBOARD:
                    sideboard.extend(cards)

        try:
            return Deck(mainboard, sideboard, commander, companion, metadata=self._metadata)
        except (ParsingError, InvalidDeck) as err:
            if self._throttled:
                raise
            _log.warning(f"Scraping failed with: {err}")
            return None


@http_requests_counted("scraping meta decks")
@timed("scraping meta decks", precision=1)
def scrape_meta(fmt="standard") -> list[Deck]:
    fmt = fmt.lower()
    if fmt not in all_formats():
        raise ValueError(f"Invalid format: {fmt!r}. Can be only one of: {all_formats()}")
    url = f"https://www.mtggoldfish.com/metagame/{fmt}/full"
    soup = throttled_soup(url, headers=GoldfishScraper.HEADERS)
    tiles = soup.find_all("div", class_="archetype-tile")
    if not tiles:
        raise ScrapingError("No deck tiles tags found")
    decks, metas = [], []
    for i, tile in enumerate(tiles, start=1):
        link = tile.find("a").attrs["href"]
        try:
            deck = GoldfishScraper(
                f"https://www.mtggoldfish.com{link}", {"format": fmt}, throttled=True).deck
        except InvalidDeck as err:
            raise ScrapingError(f"Scraping meta deck failed with: {err}")
        count = tile.find("span", class_="archetype-tile-statistic-value-extra-data").text.strip()
        count = extract_int(count)
        metas.append({"place": i, "count": count})
        decks.append(deck)
    total = sum(m["count"] for m in metas)
    for deck, meta in zip(decks, metas):
        meta["share"] = meta["count"] * 100 / total
        deck.update_metadata(meta=meta)
        deck.update_metadata(mode=Mode.BO3.value)
    return decks
