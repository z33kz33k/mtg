"""

    mtg.deck.scrapers.cardsrealm.py
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Scrape Cardsrealm decklists.

    @author: z33k

"""
import logging

import dateutil.parser

from mtg import Json
from mtg.deck.scrapers import ContainerScraper, DeckScraper
from mtg.utils.scrape import ScrapingError, dissect_js, getsoup, strip_url_params

_log = logging.getLogger(__name__)


def to_eng_url(url: str, lang_code_delimiter: str) -> str:
    if len(lang_code_delimiter) < 3 or any(
            ch != "/" for ch in (lang_code_delimiter[0], lang_code_delimiter[-1])):
        raise ValueError(f"Invalid language code delimiter: {lang_code_delimiter!r}")
    # attempt to replace any language code other than 'en-us' with 'en-us'
    _, first = url.split("mtg.cardsrealm.com/", maxsplit=1)
    if first.startswith(lang_code_delimiter[1:]):  # no lang code in url (implicitly means 'en-us')
        return url
    lang, _ = first.split(lang_code_delimiter, maxsplit=1)
    return url.replace(f"/{lang}/", "/en-us/")


@DeckScraper.registered
class CardsrealmScraper(DeckScraper):
    """Scraper of Cardsrealm decklist page.
    """
    def __init__(self, url: str, metadata: Json | None = None) -> None:
        super().__init__(url, metadata)
        self._json_data: Json | None = None

    @staticmethod
    def is_deck_url(url: str) -> bool:  # override
        return "cardsrealm.com/" in url.lower() and "/decks/" in url.lower()

    @staticmethod
    def sanitize_url(url: str) -> str:  # override
        url = strip_url_params(url, with_endpoint=False)
        return to_eng_url(url, "/decks/")

    def _get_json(self) -> Json:
        def process(text: str) -> str:
            obj, _ = text.rsplit("]", maxsplit=1)
            return obj + "]"
        return dissect_js(
            self._soup, "var deck_cards = ", 'var torneio_type =', end_processor=process)

    def _pre_parse(self) -> None:  # override
        self._soup = getsoup(self.url)
        if not self._soup:
            raise ScrapingError("Page not available")
        self._json_data = self._get_json()

    def _parse_metadata(self) -> None:  # override
        card_data = self._json_data[0]
        self._metadata["name"] = card_data["deck_title"]
        self._metadata["date"] = dateutil.parser.parse(card_data["deck_lastchange"]).date()
        self._metadata["author"] = card_data["givenNameUser"]
        self._metadata["views"] = card_data["deck_views"]
        self._update_fmt(card_data["tour_type_name"].lower())

    def _parse_card_json(self, card_json: Json) -> None:
        name = card_json["name_of_card"]
        quantity = card_json["deck_quantity"]
        card = self.find_card(name)
        if card_json["deck_sideboard"]:
            self._sideboard += self.get_playset(card, quantity)
        else:
            self._maindeck += self.get_playset(card, quantity)

    def _parse_deck(self) -> None:  # override
        for card_data in self._json_data:
            self._parse_card_json(card_data)
        self._derive_commander_from_sideboard()


@ContainerScraper.registered
class CardsrealmUserScraper(ContainerScraper):
    """Scraper of Cardsrealm user profile page.
    """
    CONTAINER_NAME = "Cardsrealm user"  # override
    DECK_URL_TEMPLATE = "https://mtg.cardsrealm.com{}"
    _DECK_SCRAPER = CardsrealmScraper  # override

    @staticmethod
    def is_container_url(url: str) -> bool:  # override
        return all(t in url.lower() for t in ("cardsrealm.com/", "/profile/", "/decks"))

    @staticmethod
    def sanitize_url(url: str) -> str:  # override
        url = strip_url_params(url, with_endpoint=False)
        return to_eng_url(url, "/profile/")

    def _collect(self) -> list[str]:  # override
        self._soup = getsoup(self.url)
        if not self._soup:
            _log.warning("User data not available")
            return []

        deck_divs = [
            div for div in self._soup.find_all("div", class_=lambda c: c and "deck_div_all" in c)]
        deck_tags = [d.find("a", href=lambda h: h and "/decks/" in h) for d in deck_divs]
        urls = [tag.attrs["href"] for tag in deck_tags]
        return [self.DECK_URL_TEMPLATE.format(url) for url in urls]
