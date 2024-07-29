"""

    mtgcards.decks.aetherhub.py
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Parse AetherHub decklist page.

    @author: z33k

"""
import logging
from datetime import datetime

from bs4 import Tag

from mtgcards.const import Json
from mtgcards.decks import Archetype, Deck, InvalidDeckError, Mode, DeckScraper, get_playset
from mtgcards.scryfall import Card, all_sets
from mtgcards.utils import extract_float, extract_int
from mtgcards.utils.scrape import ScrapingError, getsoup


_log = logging.getLogger(__name__)


class AetherhubScraper(DeckScraper):
    """Scraper of Aetherhub decklist page.

    Note:
        Companions are part of a sideboard list and aren't listed separately.
    """
    FORMATS = {
        "Arena Standard": ("standard", Mode.BO1),
        "Standard": ("standard", Mode.BO3),
        "Alchemy": ("alchemy", Mode.BO1),
        "Traditional Alchemy": ("alchemy", Mode.BO3),
        "Historic": ("historic", Mode.BO1),
        "Traditional Historic": ("historic", Mode.BO3),
        "Explorer": ("explorer", Mode.BO1),
        "Traditional Explorer": ("explorer", Mode.BO3),
        "Timeless": ("timeless", Mode.BO1),
        "Traditional Timeless": ("timeless", Mode.BO3),
        "Brawl": ("standardbrawl", Mode.BO3),
        "Historic Brawl": ("brawl", Mode.BO3),
        "Pioneer": ("pioneer", Mode.BO3),
        "Modern": ("modern", Mode.BO3),
        "Legacy": ("legacy", Mode.BO3),
        "Vintage": ("vintage", Mode.BO3),
        "Commander": ("commander", Mode.BO3),
        "Oathbreaker": ("oathbreaker", Mode.BO3),
    }

    def __init__(self, url: str, metadata: Json | None = None, throttled=False) -> None:
        super().__init__(url, metadata)
        self._throttled = throttled
        self._soup = getsoup(url)
        self._update_metadata()
        self._deck = self._get_deck()

    @staticmethod
    def is_deck_url(url: str) -> bool:  # override
        return "aetherhub.com/Deck/" in url

    def _update_metadata(self) -> None:  # override
        self._metadata["source"] = "aetherhub.com"

        # name and format
        if title_tag := self._soup.find("h2", class_="text-header-gold"):
            fmt_part, name_part = title_tag.text.strip().split("-", maxsplit=1)
            fmt_part = fmt_part.strip()
            if fmt_pair := self.FORMATS.get(fmt_part):
                fmt, mode = fmt_pair
                if fmt != self.fmt:
                    if self.fmt:
                        _log.warning(
                                f"Earlier specified format: {self.fmt!r} overwritten with a "
                                f"scraped one: {fmt!r}")
                    self._metadata["format"] = fmt
                self._metadata["mode"] = mode.value
            self._metadata["name"] = name_part.strip()

        # author (only in user-submitted decklists)
        if not self.author:
            if author_tag := self._soup.find('a', href=lambda href: href and "/User/" in href):
                self._metadata["author"] = author_tag.text

        # date and other (only in user-submitted decklists)
        if date_tags := self._soup.select(
            "div.col-xs-7.col-sm-7.col-md-7.col-lg-7.pl-0.pr-0.text-left"):
            date_tag = date_tags[0]
            date_lines = [l.strip() for l in date_tag.text.strip().splitlines() if l]
            date_text = date_lines[0].removeprefix("Last Updated: ").strip()
            self._metadata["date"] = datetime.strptime(date_text, "%d %b %Y").date()
            self._metadata["views"] = int(date_lines[2])
            self._metadata["exports"] = int(date_lines[3])
            self._metadata["comments"] = int(date_lines[4])

        # archetype
        if archetype_tag := self._soup.find("div", class_="archetype-tag"):
            archetype = archetype_tag.text.strip().lower()
            if archetype in {a.value for a in Archetype}:
                self._metadata["archetype"] = archetype

        # meta (only in meta-decklists)
        if meta_tag := self._soup.find("h5", class_="text-center"):
            text = meta_tag.text.strip()
            share_part, change_part = text.split("of meta")
            self._metadata["meta"]["share"] = extract_float(share_part)
            self._metadata["meta"]["share_change"] = extract_float(change_part)

            count_tag = self._soup.select("h4.text-center.pt-2")[0]
            count_text, _ = count_tag.text.strip().split("decks,")
            self._metadata["meta"]["count"] = extract_int(count_text)

    def _get_deck(self) -> Deck | None:  # override
        mainboard, sideboard, commander = [], [], None

        tables = self._soup.select("table.table.table-borderless.bg-ae-dark")
        if not tables:
            raise ScrapingError(
                f"No tables (that contain grouped card data) in the soup")

        hovers = []
        for table in tables:
            hovers.append([*table.find_all("div", "hover-imglink")])
        hovers = [h for h in hovers if h]
        hovers = sorted([h for h in hovers if h], key=lambda h: len(h), reverse=True)

        if len(hovers[-1]) == 1:  # may be a commander
            hovers, commander_tag = hovers[:-1], hovers[-1][0]
            result = self._parse_hover_tag(commander_tag)
            if result:
                if (len(result) == 1 and result[0].is_legendary
                        and (result[0].is_creature or result[0].is_planeswalker)):
                    commander = result[0]
                else:
                    sideboard = result

        if len(hovers) == 2:
            main_list_tags, sideboard_tags = hovers
        elif len(hovers) == 1:
            main_list_tags, sideboard_tags = hovers[0], []
        else:
            raise ScrapingError(
                f"Unexpected number of 'hover-imglink' div tags (that contain card data): "
                f"{len(hovers)}")

        for tag in main_list_tags:
            mainboard.extend(self._parse_hover_tag(tag))

        if not sideboard:
            for tag in sideboard_tags:
                sideboard.extend(self._parse_hover_tag(tag))

        try:
            return Deck(mainboard, sideboard, commander, metadata=self._metadata)
        except InvalidDeckError as err:
            if self._throttled:
                raise
            _log.warning(f"Scraping failed with: {err}")
            return None

    def _parse_hover_tag(self, hover_tag: Tag) -> list[Card]:
        quantity, *_ = hover_tag.text.split()
        quantity = extract_int(quantity)

        card_tag = hover_tag.find("a")
        if card_tag is None:
            raise ScrapingError(f"No 'a' tag inside 'hover-imglink' div tag: {hover_tag!r}")

        name, set_code = card_tag.attrs["data-card-name"], card_tag.attrs["data-card-set"].lower()
        set_code = set_code if set_code in set(all_sets()) else ""
        return get_playset(name, quantity, set_code, self.fmt)
