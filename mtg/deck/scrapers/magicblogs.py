"""

    mtg.deck.scrapers.magicblogs.py
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Scrape MagicBlogs.de decklists.

    @author: z33k

"""
import logging
from datetime import datetime

from bs4 import Tag

from mtg.deck.scrapers import DeckTagsContainerScraper, TagBasedDeckParser
from mtg.utils.scrape import ScrapingError, getsoup, strip_url_query

_log = logging.getLogger(__name__)


class MagicBlogsDeckTagParser(TagBasedDeckParser):
    """Parser of MagicBlogs.de decklist HTML tag.
    """
    def _parse_metadata(self) -> None:  # override
        pass

    def _sift(self) -> list[Tag]:
        matching_tds = []
        for td in self._deck_tag.find_all('td'):
            divs = td.find_all('div', recursive=False)
            uls = td.find_all('ul', recursive=False)
            if divs and uls:
                matching_tds.append(td)
        if len(matching_tds) not in (1, 2):
            raise ScrapingError(f"Unexpected number of <td> tags: {len(matching_tds)}")
        return matching_tds

    def _parse_td_tag(self, td_tag: Tag) -> None:
        for tag in td_tag.find_all(["div", "li"]):
            if tag.name == "div":
                if "Sideboard" in tag.text:
                    self._state.shift_to_sideboard()
                continue
            qty_tag = tag.find("span", class_="count")
            if qty_tag is None:
                raise ScrapingError("Card quantity not available")
            qty = int(qty_tag.text)
            name_tag = tag.find("span", class_="cardname")
            if name_tag is None:
                raise ScrapingError("Card name not available")
            name = name_tag.text
            if self._state.is_maindeck:
                self._maindeck += self.get_playset(self.find_card(name), qty)
            elif self._state.is_sideboard:
                self._sideboard += self.get_playset(self.find_card(name), qty)

    def _parse_decklist(self) -> None:  # override
        main_td, *side_td = self._sift()

        self._state.shift_to_maindeck()
        self._parse_td_tag(main_td)
        if side_td:
            self._parse_td_tag(side_td[0])

        self._derive_commander_from_sideboard()


@DeckTagsContainerScraper.registered
class MagicBlogsArticleScraper(DeckTagsContainerScraper):
    """Scraper of MagicBlogs.de article page.
    """
    CONTAINER_NAME = "MagicBlogs.de article"
    _DECK_PARSER = MagicBlogsDeckTagParser
    _MONTHS = {
        'Januar': 'January',
        'Februar': 'February',
        'März': 'March',
        'April': 'April',
        'Mai': 'May',
        'Juni': 'June',
        'Juli': 'July',
        'August': 'August',
        'September': 'September',
        'Oktober': 'October',
        'November': 'November',
        'Dezember': 'December'
    }

    @staticmethod
    def is_container_url(url: str) -> bool:  # override
        return f"magicblogs.de/blog/" in url.lower()

    @staticmethod
    def sanitize_url(url: str) -> str:  # override
        return strip_url_query(url)

    @classmethod
    def _parse_date(cls, date_text: str) -> datetime.date:
        day, month, year = date_text.split()
        day = day.strip('.')
        # convert German month to English
        english_month = cls._MONTHS.get(month)
        if not english_month:
            raise ScrapingError(f"Unknown month: {month}")
        # create a date string in a format that can be parsed by strptime
        english_date_string = f"{day} {english_month} {year}"
        # parse the date
        return datetime.strptime(english_date_string, "%d %B %Y").date()

    def _parse_metadata(self) -> None:
        if fmt_tag := self._soup.find("a", rel="category tag"):
            dummy = MagicBlogsDeckTagParser(fmt_tag)
            dummy.update_fmt(fmt_tag.text)
            self._metadata.update(dummy.metadata)
        self._metadata["name"] = self._soup.find("title").text
        if author_tag := self._soup.find("a", rel="author"):
            self._metadata["author"] = author_tag.text
        if time_tag := self._soup.find("time", class_="published"):
            self._metadata["date"] = self._parse_date(time_tag.text)

    def _collect(self) -> list[Tag]:  # override
        self._soup = getsoup(self.url)
        if not self._soup:
            _log.warning(self._error_msg)
            return []

        deck_tags = [*self._soup.find_all("div", class_="mtgh")]
        if not deck_tags:
            _log.warning(self._error_msg)
            return []

        self._parse_metadata()

        return deck_tags
