"""

    mtgcards.decks.cardhoarder.py
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Parse Cardhoarder decklist page.

    @author: z33k

"""
import json
import logging

from mtgcards.const import Json
from mtgcards.decks import Deck, DeckScraper, InvalidDeck
from mtgcards.utils.scrape import ScrapingError, getsoup

_log = logging.getLogger(__name__)


# Cardhoarder has anti-scraping protection (I doubt they care much about user-posted decks
# though), so there's no guarantee how long requesting with the headers below will work
class CardhoarderScraper(DeckScraper):
    """Scraper of Cardhoarder decklist page.
    """
    HEADERS = {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,"
                  "image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
        "Accept-Encoding": "gzip, deflate, br, zstd",
        "Accept-Language": "en-US,en;q=0.9",
        "Cache-Control": "max-age=0",
        "Cookie": "visid_incap_839682=Bs8kKU90R/iZbhO9/VwRZCN+r2YAAAAAQUIPAAAAAACDeQHeum1jt7r4RGPwDxR+; incap_ses_521_839682=g3VYAdW4uX4OUi5G4PY6ByN+r2YAAAAA/xh5hGR4pum/tGcc93TSwA==; CHSESSION=2tqt0ummb75vpeja8ebaa6utg5; App[AnonymousId]=Q2FrZQ%3D%3D.G7rxlng40IpehzcojCrJwLqmKUNggMcMqSl3YJUo8nwkJBJbvPrpt0QE7SfFYBy6vw39K11v7vmoo9hATO3YZ5Fr%2B5asDYpt9Ov43s7h1oa9gIEyeCbhXZTLgwmNWIaX3fw%3D; App[PaymentMethod]=Q2FrZQ%3D%3D.mHwK%2Bol%2FL%2Fg7H9HGoVz5Yxy2b2egQzIzbmJcQawQJtokJLb13RROoVqx9AdofhnUG5m9Z%2FcYna%2B6oVXZg0lVlHyK; intercom-id-jv6shdwn=cea93332-214a-410f-8350-dd9f521f1cf4; intercom-session-jv6shdwn=; intercom-device-id-jv6shdwn=c3cb412c-4f4c-4a32-af84-076820fb2159",
        "Priority": "u=0, i",
        "Referer": "https://www.cardhoarder.com/d/64560b121b70c",
        "Sec-Ch-Ua": "\"Not/A)Brand\";v=\"8\", \"Chromium\";v=\"126\", \"Google Chrome\";v=\"126\"",
        "Sec-Ch-Ua-Mobile": "?0",
        "Sec-Ch-Ua-Platform": "\"Linux\"",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "same-origin",
        "Sec-Fetch-User": "?1",
        "Upgrade-Insecure-Requests": "1",
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Chrome/126.0.0.0 Safari/537.36",
    }

    def __init__(self, url: str, metadata: Json | None = None) -> None:
        super().__init__(url, metadata)
        self._soup = getsoup(url, headers=self.HEADERS)
        self._deck_data = self._get_deck_data()
        self._scrape_metadata()
        self._deck = self._get_deck()

    @staticmethod
    def is_deck_url(url: str) -> bool:  # override
        return "www.cardhoarder.com/d/" in url

    def _get_deck_data(self) -> Json:
        deck_tag = self._soup.find("div", id="deck-viewer")
        if not deck_tag:
            raise ScrapingError(
                "No deck tag in the requested page code. You're probably being blocked by "
                "Cardhoarder anti-bot measures")
        return json.loads(deck_tag.attrs["data-deck"])

    def _scrape_metadata(self) -> None:  # override
        self._metadata["name"] = self._deck_data["name"]

    # TODO: commander, companion (example decks with such data needed)
    def _parse_deck_data(self) -> Deck:
        mainboard, sideboard = [], []
        card_jsons = []
        for _, item in self._deck_data["items"].items():
            card_jsons += item["items"]

        for data in card_jsons:
            name = data["SavedDeckItem"]["name"]
            quantity_main = int(data["SavedDeckItem"]["quantity_main"])
            quantity_sideboard = int(data["SavedDeckItem"]["quantity_sideboard"])
            card = self.find_card(name)
            mainboard += self.get_playset(card, quantity_main)
            if quantity_sideboard:
                sideboard += self.get_playset(card, quantity_sideboard)

        return Deck(mainboard, sideboard, metadata=self._metadata)

    def _get_deck(self) -> Deck | None:  # override
        try:
            return self._parse_deck_data()
        except InvalidDeck as err:
            _log.warning(f"Scraping failed with: {err}")
            return None
