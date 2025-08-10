"""

    mtg.deck.scrapers.flexslot
    ~~~~~~~~~~~~~~~~~~~~~~~~~~
    Scrape Flexslot.gg decklists.

    @author: z33k

"""
import logging
from typing import Type, override

import dateutil.parser

from mtg import Json, SECRETS
from mtg.deck.scrapers import DeckScraper, DeckUrlsContainerScraper, DecksJsonContainerScraper, \
    JsonBasedDeckParser, is_in_domain_but_not_main
from mtg.utils.scrape import InaccessiblePage, ScrapingError, request_json, strip_url_query

_log = logging.getLogger(__name__)
HEADERS = {
    "Host": "api.flexslot.gg",
    "User-Agent": "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:135.0) Gecko/20100101 Firefox/135.0",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.5",
    "Accept-Encoding": "gzip, deflate, br, zstd",
    "X-Cookie-Consent": "true",
    "X-API-Key": SECRETS["flexslot"]["api_key"],
    "X-CSRFToken" : "",
    "Origin": "https://flexslot.gg",
    "Connection": "keep-alive",
    "Referer": "https://flexslot.gg/",
    "Cookie": SECRETS["flexslot"]["cookie"],
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-site",
    "TE": "trailers",
}


def _get_json_data(url: str, scraper: Type[DeckScraper]) -> Json:
    json_data = request_json(
        url.replace("https://flexslot.gg", "https://api.flexslot.gg"),
        headers=HEADERS)
    if not json_data or not json_data.get("data"):
        raise ScrapingError("Data not available", scraper=scraper, url=url)
    return json_data["data"]


class FlexslotDeckJsonParser(JsonBasedDeckParser):
    """Parser of Flexslot.gg deck JSON data.
    """
    @override
    def _parse_metadata(self) -> None:
        self._metadata["name"] = self._deck_data["name"]
        self._metadata["author"] = self._deck_data["creator"]
        self._update_fmt(self._deck_data["format"].lower())
        self._metadata["date"] = dateutil.parser.parse(self._deck_data["date_updated"]).date()
        self._metadata["likes"] = self._deck_data["likes"]
        self._metadata["views"] = self._deck_data["pageviews"]
        if event_name := self._deck_data.get("event_name"):
            self._metadata["event"] = {"name": event_name}
            if event_date := self._deck_data.get("event_date"):
                self._metadata["event"]["date"] = dateutil.parser.parse(event_date).date()
            if player := self._deck_data.get("player"):
                self._metadata["event"]["player"] = player
            if rank := self._deck_data.get("rank"):
                self._metadata["event"]["rank"] = rank
        if archetype := self._deck_data.get("archetype"):
            self._update_archetype_or_theme(archetype)

    def _parse_card_json(self, card_json: Json) -> None:
        quantity = card_json["quantity"]
        name = card_json["card"]["name"]
        scryfall_id = card_json["card"]["id"]
        card = self.find_card(name, scryfall_id=scryfall_id)
        playset = self.get_playset(card, quantity)
        portion = card_json["deck_portion"]
        if portion == "side":
            self._sideboard.extend(playset)
        elif portion == "main":
            self._maindeck.extend(playset)

    @override
    def _parse_deck(self) -> None:
        for card_json in self._deck_data["deck_card_maps"]:
            self._parse_card_json(card_json)
        self._derive_commander_from_sideboard()


@DeckScraper.registered
class FlexslotDeckScraper(DeckScraper):
    """Scraper of Flexslot.gg decklist page.
    """
    @staticmethod
    @override
    def is_valid_url(url: str) -> bool:
        return is_in_domain_but_not_main(url, "flexslot.gg/decks/")

    @staticmethod
    @override
    def sanitize_url(url: str) -> str:
        return strip_url_query(url).removesuffix("/view")

    @override
    def _pre_parse(self) -> None:
        self._data = _get_json_data(self.url, type(self))

    @override
    def _get_sub_parser(self) -> FlexslotDeckJsonParser:
        return FlexslotDeckJsonParser(self._data, self._metadata)

    @override
    def _parse_metadata(self) -> None:
        pass

    @override
    def _parse_deck(self) -> None:
        pass


@DecksJsonContainerScraper.registered
class FlexslotSideboardScraper(DecksJsonContainerScraper):
    """Scraper of Flexslot.gg sideboard guide page.
    """
    CONTAINER_NAME = "Flexslot sideboard"  # override
    JSON_BASED_DECK_PARSER = FlexslotDeckJsonParser  # override

    @staticmethod
    @override
    def is_valid_url(url: str) -> bool:
        return is_in_domain_but_not_main(url, "flexslot.gg/sideboards/")

    @staticmethod
    @override
    def sanitize_url(url: str) -> str:
        return FlexslotDeckScraper.sanitize_url(url)

    @override
    def _collect(self) -> list[Json]:
        json_data = _get_json_data(self.url, type(self))
        if not json_data.get("decks"):
            if json_data.get("visibility") == "Patreon Exclusive":
                raise InaccessiblePage(
                    "Content paywalled (Patreon exclusive)", type(self), self.url)
            raise ScrapingError("Decks data not found", type(self), self.url)
        return json_data["decks"]


# TODO: scrape sideboards and articles too
@DeckUrlsContainerScraper.registered
class FlexslotUserScraper(DeckUrlsContainerScraper):
    """Scraper of Flexslot user page.
    """
    SELENIUM_PARAMS = {  # override
        "xpath": '//a[contains(@href, "/decks/")]',
        "consent_xpath": "//p[text()='Consent']",
        "wait_for_all": True
    }
    CONTAINER_NAME = "Flexslot user"  # override
    THROTTLING = DeckUrlsContainerScraper.THROTTLING * 2  # override
    DECK_SCRAPERS = FlexslotDeckScraper,  # override
    DECK_URL_PREFIX = "https://flexslot.gg"  # override

    @staticmethod
    @override
    def is_valid_url(url: str) -> bool:
        return "flexslot.gg/u/" in url.lower()

    @staticmethod
    @override
    def sanitize_url(url: str) -> str:
        return strip_url_query(url)

    @override
    def _collect(self) -> list[str]:
        return [t["href"] for t in self._soup.find_all("a", href=lambda h: h and "/decks/" in h)]
