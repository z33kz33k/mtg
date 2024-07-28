"""

    mtgcards.decks.goldfish.py
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Parse MtGGoldfish decklists.

    @author: z33k

"""
from datetime import datetime

from bs4 import Tag

from mtgcards.const import Json
from mtgcards.decks import Deck, DeckParser, InvalidDeckError, ParsingState
from mtgcards.scryfall import Card, all_formats, all_sets
from mtgcards.utils import extract_int, timed
from mtgcards.utils.scrape import ScrapingError, getsoup, http_requests_counted, throttled_soup


def _shift_to_commander(current_state: ParsingState) -> ParsingState:
    if current_state not in (ParsingState.IDLE, ParsingState.COMPANION):
        raise RuntimeError(f"Invalid transition to COMMANDER from: {current_state.name}")
    return ParsingState.COMMANDER


def _shift_to_companion(current_state: ParsingState) -> ParsingState:
    if current_state not in (ParsingState.IDLE, ParsingState.COMMANDER):
        raise RuntimeError(f"Invalid transition to COMPANION from: {current_state.name}")
    return ParsingState.COMPANION


def _shift_to_mainboard(current_state: ParsingState) -> ParsingState:
    if current_state not in (ParsingState.IDLE, ParsingState.COMMANDER, ParsingState.COMPANION):
        raise RuntimeError(f"Invalid transition to MAINBOARD from: {current_state.name}")
    return ParsingState.MAINBOARD


def _shift_to_sideboard(current_state: ParsingState) -> "ParsingState":
    if current_state is not ParsingState.MAINBOARD:
        raise RuntimeError(f"Invalid transition to SIDEBOARD from: {current_state.name}")
    return ParsingState.SIDEBOARD


class GoldfishParser(DeckParser):
    """Parser of MtGGoldfish decklist page.
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

    def __init__(self, url: str, fmt="standard", author="", throttled=False) -> None:
        super().__init__(fmt, author)
        self._throttled = throttled
        self._soup = throttled_soup(
            url, headers=self.HEADERS) if self._throttled else getsoup(url, headers=self.HEADERS)
        self._metadata = self._get_metadata()
        self._deck = self._get_deck()

    def _get_metadata(self) -> Json:
        metadata = {}
        title_tag = self._soup.find("h1", class_="title")
        metadata["source"] = "www.mtggoldfish.com"
        metadata["name"], *_ = title_tag.text.strip().split("\n")
        metadata["format"] = self._fmt
        if self._author:
            metadata["author"] = self._author
        else:
            author_tag = title_tag.find("span")
            if author_tag is not None:
                metadata["author"] = author_tag.text.strip().removeprefix("by ")
        info_tag = self._soup.find("p", class_="deck-container-information")
        lines = [l for l in info_tag.text.splitlines() if l]
        source_idx = None
        for i, line in enumerate(lines):
            if line.startswith("Format:"):
                fmt = line.removeprefix("Format:").strip().lower()
                if fmt in self.FMT_NAMES:
                    fmt = self.FMT_NAMES[fmt]
                if fmt in all_formats():
                    self._fmt = fmt
                    metadata["format"] = fmt
            elif line.startswith("Event:"):
                metadata["event"] = line.removeprefix("Event:").strip()
            elif line.startswith("Deck Source:"):
                source_idx = i + 1
            elif line.startswith("Deck Date:"):
                metadata["date"] = datetime.strptime(
                    line.removeprefix("Deck Date:").strip(), "%b %d, %Y").date()
        if source_idx is not None:
            metadata["original_source"] = lines[source_idx].strip()
        return metadata

    def _get_deck(self) -> Deck | None:  # override
        mainboard, sideboard, commander, companion = [], [], None, None
        table = self._soup.find("table", class_="deck-view-deck-table")
        rows = table.find_all("tr")
        headers = (
            "Creatures", "Planeswalkers", "Spells", "Battles", "Artifacts", "Enchantments", "Lands")
        for row in rows:
            if row.has_attr("class") and "deck-category-header" in row.attrs["class"]:
                if row.text.strip() == "Commander":
                    self._state = _shift_to_commander(self._state)
                elif row.text.strip().startswith("Companion"):
                    self._state = _shift_to_companion(self._state)
                elif any(h in row.text.strip() for h in headers
                         ) and self._state is not ParsingState.MAINBOARD:
                    self._state = _shift_to_mainboard(self._state)
                elif "Sideboard" in row.text.strip():
                    self._state = _shift_to_sideboard(self._state)
            else:
                cards = self._parse_row(row)
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
        except InvalidDeckError:
            if self._throttled:
                raise
            return None

    def _parse_row(self, row: Tag) -> list[Card]:
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
        name, set_code = text.split("[")
        name = name.strip()
        if "<" in name:
            name, *rest = name.split("<")
            name = name.strip()

        set_code = set_code[:-1].lower()
        set_code = set_code if set_code in set(all_sets()) else ""
        return self._get_playset(name, quantity, set_code)


@http_requests_counted("scraping meta decks")
@timed("scraping meta decks", precision=1)
def scrape_meta(fmt="standard") -> list[Deck]:
    fmt = fmt.lower()
    if fmt not in all_formats():
        raise ValueError(f"Invalid format: {fmt!r}. Can be only one of: {all_formats()}")
    url = f"https://www.mtggoldfish.com/metagame/{fmt}/full"
    soup = throttled_soup(url, headers=GoldfishParser.HEADERS)
    tiles = soup.find_all("div", class_="archetype-tile")
    if not tiles:
        raise ScrapingError("No deck tiles tags found")
    decks, counts = [], []
    for i, tile in enumerate(tiles, start=1):
        link = tile.find("a").attrs["href"]
        try:
            deck = GoldfishParser(
                f"https://www.mtggoldfish.com{link}", fmt=fmt, throttled=True).deck
        except InvalidDeckError as err:
            raise ScrapingError(f"Scraping meta deck failed with: {err}")
        count = tile.find("span", class_="archetype-tile-statistic-value-extra-data").text.strip()
        count = extract_int(count)
        counts.append(count)
        deck.update_metadata(meta_place=i, meta_count=count)
        decks.append(deck)
    total = sum(counts)
    for deck, count in zip(decks, counts):
        deck.update_metadata(meta_share=count * 100 / total)
    return decks
