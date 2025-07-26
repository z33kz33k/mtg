"""

    mtg.deck.scrapers.hareruya
    ~~~~~~~~~~~~~~~~~~~~~~~~~~
    Scrape Hareruya decklists.

    @author: z33k

"""
import logging
from typing import override

import dateutil.parser
from bs4 import NavigableString, Tag

from mtg import HybridContainerScraper, Json, SECRETS
from mtg.deck.scrapers import Collected, DeckScraper, DeckUrlsContainerScraper, JsonBasedDeckParser, \
    is_in_domain_but_not_main
from mtg.deck.scrapers.goldfish import HEADERS as GOLDFISH_HEADERS
from mtg.utils.scrape import ScrapingError, request_json

_log = logging.getLogger(__name__)


def get_source(src: str) -> str | None:
    if ".hareruyamtg.com" in src:
        _, *parts = src.split(".")
        return ".".join(parts)
    return None


@DeckScraper.registered
class InternationalHareruyaDeckScraper(DeckScraper):
    """Scraper of international Hareruya decklist page.
    """
    HEADERS = GOLDFISH_HEADERS  # override

    @staticmethod
    @override
    def is_valid_url(url: str) -> bool:
        url = url.lower()
        return ("hareruyamtg.com" in url and "/deck/" in url
                and "deck.hareruyamtg.com/deck/" not in url
                and "/result" not in url
                and "/bulk/" not in url  # shopping cart URL
                and "/metagame" not in url)

    @staticmethod
    @override
    def sanitize_url(url: str) -> str:
        return url.replace("/ja/","/en/")

    @override
    def _parse_metadata(self) -> None:
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
                self._update_archetype_or_theme(value_tag.text.strip())
            elif cat_tag.text.strip() == "Player":
                self._metadata["author"] = value_tag.text.strip()
            elif cat_tag.text.strip() == "Score":
                self._metadata["event_score"] = value_tag.text.strip()
            elif cat_tag.text.strip() == "Date":
                self._metadata["date"] = dateutil.parser.parse(value_tag.text.strip()).date()

        if not self._metadata.get("name") and self._metadata.get("hareruya_archetype"):
            self._metadata["name"] = self._metadata["hareruya_archetype"]

    @override
    def _parse_deck(self) -> None:
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


class JapaneseHareruyaDeckJsonParser(JsonBasedDeckParser):
    """Parser of Japanese Hareruya deck JSON data.
    """
    @override
    def _parse_metadata(self) -> None:
        fmt = self._deck_data["format_name_en"]
        self._update_fmt(fmt)
        self._metadata["name"] = self._deck_data["deck_name"]
        self._metadata["author"] = self._deck_data["nickname"]
        if arch := self._deck_data.get("archetype_name_en"):
            self._update_archetype_or_theme(arch)
        self._metadata["deck_type"] = self._deck_data["deck_type"]
        if event_name := self._deck_data.get("event_name_en"):
            self._metadata.setdefault("event", {})
            self._metadata["event"]["name"] = event_name
        if event_date := self._deck_data.get("event_date"):
            self._metadata.setdefault("event", {})
            self._metadata["event"]["date"] = dateutil.parser.parse(event_date).date()
        if event_player := self._deck_data.get("player_name"):
            self._metadata.setdefault("event", {})
            self._metadata["event"]["player"] = event_player
        if event_result := self._deck_data.get("result"):
            self._metadata.setdefault("event", {})
            self._metadata["event"]["result"] = event_result
        if event_ranking := self._deck_data.get("ranking"):
            self._metadata.setdefault("event", {})
            self._metadata["event"]["ranking"] = event_ranking
        if source_url := self._deck_data.get("source_url"):
            self._metadata["original_source"] = source_url
        self._metadata["date"] = dateutil.parser.parse(self._deck_data["update_date"]).date()

    def _process_card(self, json_card: Json) -> None:
        quantity = json_card["count"]
        name = json_card["name_en"]
        if json_card["board_id"] == 1:
            self._maindeck.extend(self.get_playset(self.find_card(name), quantity))
        elif json_card["board_id"] == 2:
            self._sideboard.extend(self.get_playset(self.find_card(name), quantity))
        elif json_card["board_id"] == 3:
            self._set_commander(self.find_card(name))

    @override
    def _parse_deck(self) -> None:
        for card in self._deck_data["cards"]:
            self._process_card(card)


@DeckScraper.registered
class JapaneseHareruyaDeckScraper(DeckScraper):
    """Scraper of Japanese Hareruya decklist page.
    """
    API_URL_TEMPLATE = "https://api.deck.hareruyamtg.com/api/deck/{}?display_token={}"  # override

    @staticmethod
    @override
    def is_valid_url(url: str) -> bool:
        url = url.lower()
        return ("hareruyamtg.com/decks/list/" in url or "hareruyamtg.com/decks/" in url
                or "deck.hareruyamtg.com/deck/" in url) and "/user/" not in url

    @staticmethod
    @override
    def sanitize_url(url: str) -> str:
        if "deck.hareruyamtg.com/deck/" in url:
            return url.replace("deck.hareruyamtg.com/deck/", "www.hareruyamtg.com/decks/")
        return url

    @override
    def _get_data_from_api(self) -> Json:
        if "?display_token=" in self.url:
            rest, self._display_token = self.url.rsplit("?display_token=", maxsplit=1)
        else:
            rest, self._display_token = self.url, ""
        *_, self._decklist_id = rest.split("/")
        return request_json(
            self.API_URL_TEMPLATE.format(self._decklist_id, self._display_token))

    @override
    def _get_sub_parser(self) -> JapaneseHareruyaDeckJsonParser:
        return JapaneseHareruyaDeckJsonParser(self._data, self._metadata)

    @override
    def _parse_metadata(self) -> None:
        pass

    @override
    def _parse_deck(self) -> None:
        pass


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


@DeckUrlsContainerScraper.registered
class HareruyaEventScraper(DeckUrlsContainerScraper):
    """Scraper of Hareruya event decks search page.
    """
    CONTAINER_NAME = "Hareruya event"  # override
    HEADERS = HEADERS  # override
    DECK_SCRAPERS = InternationalHareruyaDeckScraper, JapaneseHareruyaDeckScraper  # override

    @staticmethod
    @override
    def is_valid_url(url: str) -> bool:
        return all(t in url for t in {"hareruyamtg.com", "/deck", "/result?", "eventName="})

    @override
    def _collect(self) -> list[str]:
        return [a_tag.attrs["href"] for a_tag in self._soup.find_all(
            "a", class_="deckSearch-searchResult__itemWrapper")]


@DeckUrlsContainerScraper.registered
class HareruyaPlayerScraper(DeckUrlsContainerScraper):
    """Scraper of Hareruya player decks search page.
    """
    CONTAINER_NAME = "Hareruya player"  # override
    HEADERS = HEADERS  # override
    DECK_SCRAPERS = InternationalHareruyaDeckScraper, JapaneseHareruyaDeckScraper  # override

    @staticmethod
    @override
    def is_valid_url(url: str) -> bool:
        url = url.lower()
        return all(t in url for t in {"hareruyamtg.com", "/deck", "/result?", "player="})

    @override
    def _collect(self) -> list[str]:
        return [a_tag.attrs["href"] for a_tag in self._soup.find_all(
            "a", class_="deckSearch-searchResult__itemWrapper")]


# TODO: handle cases like: https://article.hareruyamtg.com/article/44666/#4 (individual scraper
#  like what works for mtgo.com?)
# TODO: handle cases like here: https://article.hareruyamtg.com/article/89306 or
#  https://article.hareruyamtg.com/article/89077 where there's no display token for the API (the
#  deck scraper seems to handle those cases (simply, no token is then passed))
# TODO: filter out from JapaneseHareruyaDeckScraper links like this: https://www.hareruyamtg.com/decks/tile/search
# TODO: investigate if this type of URL: https://article.hareruyamtg.com/article/91545/?utm_source=video&utm_medium=column&utm_campaign=mtgyoutube_ffkoryaku
#  is not an author URL (or similar) - video: https://www.youtube.com/watch?v=cDmXK40rDbU
#  still, a very similar URL: https://article.hareruyamtg.com/article/98770/?utm_source=video&utm_medium=column&utm_campaign=mtgyoutube_deck
#  is a valid article URL and another very similar one:
#  https://article.hareruyamtg.com/article/?utm_source=video&utm_medium=column&utm_campaign
#  =mtgyoutube_article seems like a container of articles... VERY CONFUSING!
# TODO: look into channel: https://www.youtube.com/channel/UC1l7GtlvAmCOXRlxjImbWvw logs ==> 247
#  videos flagged for re-scraping!
# TODO: investigate https://article.hareruyamtg.com/article/61228 ==> decklists not detected!
# @DeckUrlsContainerScraper.registered
class HareruyaArticleScraper(HybridContainerScraper):
    """Scraper of Hareruya article page.
    """
    CONTAINER_NAME = "Hareruya article"  # override
    JSON_BASED_DECK_PARSER = JapaneseHareruyaDeckJsonParser  # override

    @staticmethod
    @override
    def is_valid_url(url: str) -> bool:
        url = url.lower()
        return is_in_domain_but_not_main(url, "article.hareruyamtg.com/article/") and not any(
            t in url for t in ("/page/", "/author/"))

    @staticmethod
    def _collect_deck_data(article_tag: Tag) -> Json:
        deck_data = []
        for tag in article_tag.find_all("deck-embedder", deckid=True, token=True):
            deck_id, token = tag.attrs["deckid"], tag.attrs["token"]
            data = request_json(
                JapaneseHareruyaDeckScraper.API_URL_TEMPLATE.format(deck_id, token))
            if data:
                deck_data.append(data)
        return deck_data

    @override
    def _collect(self) -> Collected:
        article_tag = self._soup.find("article")
        if not article_tag:
            err = ScrapingError("Article tag not found", scraper=type(self), url=self.url)
            _log.warning(f"Scraping failed with: {err!r}")
            return [], [], [], []
        deck_data = self._collect_deck_data(article_tag)
        if deck_data:
            return [], [], deck_data, []
        deck_urls, container_urls = self._get_links_from_tags(article_tag)
        return deck_urls, [], [], container_urls
