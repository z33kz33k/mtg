"""

    mtg.deck.scrapers.penny.py
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Scrape PennyDreadfulMagic decklists.

    @author: z33k

"""
import logging

from bs4 import Tag

from mtg.deck.scrapers import DeckUrlsContainerScraper, DeckScraper
from mtg.scryfall import Card
from mtg.utils import from_iterable, get_date_from_ago_text, get_date_from_month_text
from mtg.utils.scrape import ScrapingError, getsoup, request_json, strip_url_params

_log = logging.getLogger(__name__)


@DeckScraper.registered
class PennyDreadfulMagicDeckScraper(DeckScraper):
    """Scraper of PennyDreadfulMagic decklist page.
    """
    @staticmethod
    def is_deck_url(url: str) -> bool:  # override
        return "pennydreadfulmagic.com/decks/" in url.lower()

    @staticmethod
    def sanitize_url(url: str) -> str:  # override
        return strip_url_params(url)

    def _pre_parse(self) -> None:  # override
        self._soup = getsoup(self.url)
        if not self._soup:
            raise ScrapingError("Page not available")

    def _parse_metadata(self) -> None:  # override
        self._update_fmt("penny")
        self._metadata["name"] = self._soup.find("h1", class_="deck-name").text.strip()
        info_tag = self._soup.find("div", class_="title")
        if archetype_tag := info_tag.find("a", href=lambda h: h and "/archetypes/" in h):
            self._update_custom_theme("penny", archetype_tag.text.strip())
        author_tag = info_tag.find("a", href=lambda h: h and "/people/id/" in h)
        self._metadata["author"] = author_tag.text.strip()
        if date_tag := from_iterable(
            info_tag.find_all("div", class_="subtitle"), lambda t: not t.find("a")):
            date_text = date_tag.text.strip()
            if "ago" in date_text:
                self._metadata["date"] = get_date_from_ago_text(date_text)
            else:
                self._metadata["date"] = get_date_from_month_text(date_tag.text.strip())
        if event_tag := info_tag.find("a", href=lambda h: h and "/competitions/" in h):
            self._metadata["event"] = event_tag.text.strip()

    @classmethod
    def _parse_card_tag(cls, card_tag: Tag) -> list[Card]:
        text = card_tag.text.strip()
        qty_text, name = text.split(maxsplit=1)
        quantity = int(qty_text)
        return cls.get_playset(cls.find_card(name), quantity)

    def _parse_decklist(self) -> None:  # override
        for section_tag in self._soup.find_all("section"):
            if section_tag.find("section"):  # skip higher-order sections
                continue
            h2_tag = section_tag.find("h2")
            if not h2_tag:  # skip irrelevant sections
                continue
            else:
                section = h2_tag.text.strip()
                card_tags = section_tag.find_all("a", class_="card")
                for card_tag in card_tags:
                    cards = self._parse_card_tag(card_tag)

                    if "Sideboard" in section:
                        self._sideboard += cards
                    else:
                        self._maindeck += cards


@DeckUrlsContainerScraper.registered
class PennyDreadfulMagicCompetitionScraper(DeckUrlsContainerScraper):
    """Scraper of PennyDreadfulMagic competition page.
    """
    CONTAINER_NAME = "PennyDreadfulMagic competition"  # override
    API_URL_TEMPLATE = ("https://pennydreadfulmagic.com/api/decks/?achievementKey=&archetypeId=&"
                        "cardName=&competitionId={}&competitionFlagId=&deckType=&page=0&page"
                        "Size=200&personId=&q=&seasonId=")
    DECK_URL_TEMPLATE = "https://pennydreadfulmagic.com{}"
    _DECK_SCRAPER = PennyDreadfulMagicDeckScraper  # override

    @staticmethod
    def is_container_url(url: str) -> bool:  # override
        return "pennydreadfulmagic.com/competitions/" in url.lower()

    @staticmethod
    def sanitize_url(url: str) -> str:  # override
        return strip_url_params(url)

    def _get_competition_id(self) -> str:
        *_, last = self.url.split("/")
        return last

    def _collect(self) -> list[str]:  # override
        json_data = request_json(self.API_URL_TEMPLATE.format(self._get_competition_id()))
        if not json_data or not json_data.get("objects"):
            _log.warning(self._error_msg)
            return []
        return [self.DECK_URL_TEMPLATE.format(d["url"]) for d in json_data["objects"]]


@DeckUrlsContainerScraper.registered
class PennyDreadfulMagicUserScraper(DeckUrlsContainerScraper):
    """Scraper of PennyDreadfulMagic user page.
    """
    CONTAINER_NAME = "PennyDreadfulMagic user"  # override
    API_URL_TEMPLATE = ("https://pennydreadfulmagic.com/api/decks/?achievementKey=&archetypeId="
                        "&cardName=&competitionId=&competitionFlagId=&deckType=all&page=0&page"
                        "Size=200&personId={}&q=&seasonId={}")
    DECK_URL_TEMPLATE = "https://pennydreadfulmagic.com{}"
    _DECK_SCRAPER = PennyDreadfulMagicDeckScraper  # override

    @property
    def _ids_in_url(self) -> bool:
        return "/seasons/" in self.url.lower() and "/id/" in self.url.lower()

    @staticmethod
    def is_container_url(url: str) -> bool:  # override
        return "pennydreadfulmagic.com" in url.lower() and "/people/" in url.lower()

    @staticmethod
    def sanitize_url(url: str) -> str:  # override
        return strip_url_params(url)

    @staticmethod
    def _parse_url_for_ids(url: str) -> tuple[str, str]:
        url = url.removesuffix("/")
        _, last = url.split("seasons/", maxsplit=1)
        season_id, user_id = last.split("/people/id/", maxsplit=1)
        return season_id, user_id

    def _find_ids(self) -> tuple[str, str] | None:
        soup = getsoup(self.url)
        if not soup:
            return None
        season_ids, user_ids = set(), set()
        for a_tag in soup.find_all(
                "a", href=lambda h: h and "/seasons/" in h and "/people/id/" in h):
            season_id, user_id = self._parse_url_for_ids(a_tag.attrs["href"])
            season_ids.add(int(season_id))
            user_ids.add(int(user_id))
        if not season_ids or not user_ids:
            return None
        return str(max(season_ids)), str(max(user_ids))

    def _get_ids(self) -> tuple[str, str] | None:
        if self._ids_in_url:
            return self._parse_url_for_ids(self.url)
        return self._find_ids()

    def _collect(self) -> list[str]:  # override
        if ids := self._get_ids():
            season_id, user_id = ids
        else:
            _log.warning(self._error_msg)
            return []
        json_data = request_json(self.API_URL_TEMPLATE.format(user_id, season_id))
        if not json_data or not json_data.get("objects"):
            _log.warning(self._error_msg)
            return []
        return [self.DECK_URL_TEMPLATE.format(d["url"]) for d in json_data["objects"]]
