"""

    mtgcards.deck.scrapers.goldfish.py
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Scrape MtGGoldfish decklists.

    @author: z33k

"""
import logging
from datetime import datetime

from mtgcards import Json
from mtgcards.deck import Deck, Mode, ParsingState
from mtgcards.deck.scrapers import DeckScraper
from mtgcards.scryfall import all_formats
from mtgcards.utils import extract_int, timed
from mtgcards.utils.scrape import ScrapingError, getsoup, http_requests_counted, throttled_soup

_log = logging.getLogger(__name__)


# alternative approach would be to scrape:
# self._soup.find("input", id="deck_input_deck").attrs["value"] which contains a decklist in
# Arena format (albeit with the need to .replace("sideboard", "Sideboard") or maybe some other
# safer means to achieve the same effect)
# yet another alternative approach would be to scrape:
# https://www.mtggoldfish.com/deck/arena_download/{DECK_ID} but this entails another request and
# parsing a DECK_ID from the first URL
@DeckScraper.registered
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

    def __init__(
            self, url: str, metadata: Json | None = None) -> None:
        super().__init__(url, metadata)

    @staticmethod
    def is_deck_url(url: str) -> bool:  # override
        return (("www.mtggoldfish.com/deck/" in url or "www.mtggoldfish.com/archetype/" in url)
                and "/custom/" not in url)

    @staticmethod
    def sanitize_url(url: str) -> str:  # override
        if "/visual/" in url:
            url = url.replace("/visual/", "/")
        if "popout?id=" in url:
            url = url.replace("popout?id=", "")
        if "#" in url:
            url, _ = url.rsplit("#", maxsplit=1)
            return url
        return url

    def _pre_parse(self) -> None:  # override
        self._soup = getsoup(self.url, headers=self.HEADERS)
        if not self._soup:
            raise ScrapingError("Page not available")

    def _parse_metadata(self) -> None:  # override
        title_tag = self._soup.find("h1", class_="title")
        self._metadata["name"], *_ = title_tag.text.strip().split("\n")
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

    def _parse_deck(self) -> None:  # override
        deck_tag = self._soup.find("table", class_="deck-view-deck-table")
        for tag in deck_tag.descendants:
            if tag.name == "tr" and tag.has_attr(
                    "class") and "deck-category-header" in tag.attrs["class"]:
                if "Sideboard" in tag.text:
                    self._shift_to_sideboard()
                elif "Commander" in tag.text:
                    self._shift_to_commander()
                elif "Companion" in tag.text:
                    self._shift_to_companion()
                elif self._state is not ParsingState.MAINDECK:
                    self._shift_to_maindeck()
            elif tag.name == "tr":
                td_tags = tag.find_all("td")
                if td_tags and len(td_tags) >= 3:
                    qty_tag, name_tag, *_ = td_tags
                    quantity = extract_int(qty_tag.text)
                    name = name_tag.text.strip()
                    cards = self.get_playset(self.find_card(name), quantity)
                    if self._state is ParsingState.MAINDECK:
                        self._maindeck += cards
                    elif self._state is ParsingState.SIDEBOARD:
                        self._sideboard += cards
                    elif self._state is ParsingState.COMMANDER:
                        self._set_commander(cards[0])
                    elif self._state is ParsingState.COMPANION:
                        self._companion = cards[0]


@http_requests_counted("scraping meta decks")
@timed("scraping meta decks", precision=1)
def scrape_meta(fmt="standard") -> list[Deck]:
    fmt = fmt.lower()
    if fmt not in all_formats():
        raise ValueError(f"Invalid format: {fmt!r}. Can be only one of: {all_formats()}")
    url = f"https://www.mtggoldfish.com/metagame/{fmt}/full"
    soup = throttled_soup(url, headers=GoldfishScraper.HEADERS)
    if not soup:
        raise ScrapingError("Page not available")
    tiles = soup.find_all("div", class_="archetype-tile")
    if not tiles:
        raise ScrapingError("No deck tiles tags found")
    decks, metas = [], []
    for i, tile in enumerate(tiles, start=1):
        link = tile.find("a").attrs["href"]
        deck = GoldfishScraper(
            f"https://www.mtggoldfish.com{link}", {"format": fmt}).scrape(
            throttled=True, suppress_invalid_deck=False)
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
