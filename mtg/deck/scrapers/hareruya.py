"""

    mtg.deck.scrapers.hareruya.py
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Scrape Hareruya decklists.

    @author: z33k

"""
import logging

import dateutil.parser
from bs4 import NavigableString

from mtg import Json, SECRETS
from mtg.deck.scrapers import DeckUrlsContainerScraper, DeckScraper
from mtg.deck.scrapers.goldfish import HEADERS as GOLDFISH_HEADERS
from mtg.utils.scrape import ScrapingError, getsoup, request_json

_log = logging.getLogger(__name__)


@DeckScraper.registered
class InternationalHareruyaDeckScraper(DeckScraper):
    """Scraper of international Hareruya decklist page.
    """
    @staticmethod
    def is_deck_url(url: str) -> bool:  # override
        url = url.lower()
        return ("hareruyamtg.com" in url and "/deck/" in url
                and "deck.hareruyamtg.com/deck/" not in url and "/result?" not in url)

    @staticmethod
    def sanitize_url(url: str) -> str:  # override
        return url.replace("/ja/","/en/")

    def _pre_parse(self) -> None:  # override
        self._soup = getsoup(self.url, headers=GOLDFISH_HEADERS)
        if not self._soup:
            raise ScrapingError("Page not available")

    def _parse_metadata(self) -> None:  # override
        info_tag = self._soup.find("div", class_="deckSearch-deckList__information__flex")
        for ul_tag in info_tag.find_all("ul"):
            li_tags = ul_tag.find_all("li")
            if len(li_tags) != 2:
                continue
            cat_tag, value_tag = li_tags
            if cat_tag.text.strip() == "Deck Name":
                self._metadata["name"] = value_tag.text.strip()
            elif cat_tag.text.strip() == "Tournament":
                self._metadata["event"] = value_tag.text.strip()
            elif cat_tag.text.strip() == "Format":
                self._update_fmt(value_tag.text.strip())
            elif cat_tag.text.strip() == "Archetype":
                self._metadata["hareruya_archetype"] = value_tag.text.strip()
            elif cat_tag.text.strip() == "Player":
                self._metadata["author"] = value_tag.text.strip()
            elif cat_tag.text.strip() == "Score":
                self._metadata["event_score"] = value_tag.text.strip()
            elif cat_tag.text.strip() == "Date":
                self._metadata["date"] = dateutil.parser.parse(value_tag.text.strip()).date()

        if not self._metadata.get("name") and self._metadata.get("hareruya_archetype"):
            self._metadata["name"] = self._metadata["hareruya_archetype"]

    def _parse_decklist(self) -> None:  # override
        main_tag = self._soup.find("div", class_="deckSearch-deckList__deckList__wrapper")

        for sub_tag in main_tag.descendants:
            if isinstance(sub_tag, NavigableString):
                continue

            if class_ := sub_tag.attrs.get("class"):
                if "deckSearch-deckList__deckList__totalNumber" in class_:
                    if "Sideboard" in sub_tag.text:
                        self._state.shift_to_sideboard()
                    elif "Commander" in sub_tag.text:
                        self._state.shift_to_commander()
                    elif not self._state.is_maindeck:
                        self._state.shift_to_maindeck()
            else:
                name_tag = sub_tag.find("a", class_="popup_product")
                if not name_tag:
                    continue
                name = name_tag.text.strip().strip("《》")
                qty_tag = sub_tag.find("span")
                if not qty_tag:
                    continue
                quantity = int(qty_tag.text)
                cards = self.get_playset(self.find_card(name), quantity)
                if self._state.is_maindeck:
                    self._maindeck += cards
                elif self._state.is_sideboard:
                    self._sideboard += cards
                elif self._state.is_commander:
                    self._set_commander(cards[0])


@DeckScraper.registered
class JapaneseHareruyaDeckScraper(DeckScraper):
    """Scraper of Japanese Hareruya decklist page.
    """
    API_URL_TEMPLATE = "https://api.deck.hareruyamtg.com/api/deck/{}?display_token={}"

    def __init__(
            self, url: str, metadata: Json | None = None) -> None:
        super().__init__(url, metadata)
        if "?display_token=" in self.url:
            rest, self._display_token = self.url.rsplit("?display_token=", maxsplit=1)
        else:
            rest, self._display_token = self.url, ""
        *_, self._decklist_id = rest.split("/")
        self._json_data: Json | None = None

    @staticmethod
    def is_deck_url(url: str) -> bool:  # override
        url = url.lower()
        return ("hareruyamtg.com/decks/list/" in url or "hareruyamtg.com/decks/" in url
                or "deck.hareruyamtg.com/deck/" in url) and "/user/" not in url

    @staticmethod
    def sanitize_url(url: str) -> str:  # override
        if "deck.hareruyamtg.com/deck/" in url:
            return url.replace("deck.hareruyamtg.com/deck/", "www.hareruyamtg.com/decks/")
        return url

    def _pre_parse(self) -> None:  # override
        self._json_data = request_json(
            self.API_URL_TEMPLATE.format(self._decklist_id, self._display_token))
        if not self._json_data:
            raise ScrapingError("Data not available")

    def _parse_metadata(self) -> None:  # override
        fmt = self._json_data["format_name_en"]
        self._update_fmt(fmt)
        self._metadata["name"] = self._json_data["deck_name"]
        self._metadata["author"] = self._json_data["nickname"]
        if arch := self._json_data.get("archetype_name_en"):
            self._update_custom_theme("hareruya", arch)
        self._metadata["deck_type"] = self._json_data["deck_type"]
        if event_name := self._json_data.get("event_name_en"):
            self._metadata.setdefault("event", {})
            self._metadata["event"]["name"] = event_name
        if event_date := self._json_data.get("event_date"):
            self._metadata.setdefault("event", {})
            self._metadata["event"]["date"] = dateutil.parser.parse(event_date).date()
        if event_player := self._json_data.get("player_name"):
            self._metadata.setdefault("event", {})
            self._metadata["event"]["player"] = event_player
        if event_result := self._json_data.get("result"):
            self._metadata.setdefault("event", {})
            self._metadata["event"]["result"] = event_result
        if event_ranking := self._json_data.get("ranking"):
            self._metadata.setdefault("event", {})
            self._metadata["event"]["ranking"] = event_ranking
        if source_url := self._json_data.get("source_url"):
            self._metadata["original_source"] = source_url
        self._metadata["date"] = dateutil.parser.parse(self._json_data["update_date"]).date()

    def _process_card(self, json_card: Json) -> None:
        quantity = json_card["count"]
        name = json_card["name_en"]
        if json_card["board_id"] == 1:
            self._maindeck.extend(self.get_playset(self.find_card(name), quantity))
        elif json_card["board_id"] == 2:
            self._sideboard.extend(self.get_playset(self.find_card(name), quantity))
        elif json_card["board_id"] == 3:
            self._set_commander(self.find_card(name))

    def _parse_decklist(self) -> None:  # override
        for card in self._json_data["cards"]:
            self._process_card(card)


@DeckUrlsContainerScraper.registered
class HareruyaEventScraper(DeckUrlsContainerScraper):
    """Scraper of Hareruya event decks search page.
    """
    CONTAINER_NAME = "Hareruya event"  # override
    HEADERS = {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,"
                  "image/png,image/svg+xml,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Accept-Encoding": "gzip, deflate, br, zstd",
        "Connection": "keep-alive",
        "Cookie": SECRETS["hareruya"]["cookie"],
        "DNT": "1",
        "Host": "www.hareruyamtg.com",
        "Priority": "u=0, i",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "cross-site",
        "Sec-GPC": "1",
        "TE": "trailers",
        "Upgrade-Insecure-Requests": "1",
        "User-Agent": "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:131.0) Gecko/20100101 "
                      "Firefox/131.0",
    }

    @staticmethod
    def is_container_url(url: str) -> bool:  # override
        return all(t in url for t in {"hareruyamtg.com", "/deck", "/result?", "eventName="})

    def _collect(self) -> list[str]:  # override
        self._soup = getsoup(self.url, headers=self.HEADERS)
        if not self._soup:
            _log.warning(self._error_msg)
            return []

        return [a_tag.attrs["href"] for a_tag in self._soup.find_all(
            "a", class_="deckSearch-searchResult__itemWrapper")]


@DeckUrlsContainerScraper.registered
class HareruyaPlayerScraper(DeckUrlsContainerScraper):
    """Scraper of Hareruya player decks search page.
    """
    CONTAINER_NAME = "Hareruya player"  # override

    @staticmethod
    def is_container_url(url: str) -> bool:  # override
        url = url.lower()
        return all(t in url for t in {"hareruyamtg.com", "/deck", "/result?", "player="})

    def _collect(self) -> list[str]:  # override
        self._soup = getsoup(self.url, headers=HareruyaEventScraper.HEADERS)
        if not self._soup:
            _log.warning(self._error_msg)
            return []

        return [a_tag.attrs["href"] for a_tag in self._soup.find_all(
            "a", class_="deckSearch-searchResult__itemWrapper")]
