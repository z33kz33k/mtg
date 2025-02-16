"""

    mtg.mtgwiki.py
    ~~~~~~~~~~~~~~
    Handle MTG Wiki data.

    @author: z33k

"""
from bs4 import BeautifulSoup
from bs4.element import Tag

from mtg import DATA_DIR
from mtg.utils.files import download_file

FILENAME = "creature_type.html"


def download_creature_type_page() -> None:
    """Download MGT Wiki page on creature types.
    """
    url = "https://mtg.fandom.com/wiki/Creature_type"
    download_file(url, file_name=FILENAME, dst_dir=DATA_DIR)


class _CreatureTypesParser:
    """Parse MTG Wiki "Creature_type" page for possible races and classes among creature types in a
    MtG card's type line.
    """
    FILEPATH = DATA_DIR / FILENAME

    @property
    def races(self) -> list[str]:
        """Return a list of races.
        """
        return self._races

    @property
    def classes(self) -> list[str]:
        """Return a list of classes.
        """
        return self._classes

    def __init__(self) -> None:
        if not self.FILEPATH.exists():
            download_creature_type_page()
        self._markup = self.FILEPATH.read_text()
        self._soup = BeautifulSoup(self._markup, "lxml")
        self._race_table, self._class_table = self._get_tables()
        self._races = self._parse_table(self._race_table)
        self._classes = self._parse_table(self._class_table)

    def _get_tables(self) -> tuple[Tag, Tag]:
        table = self._soup.find("table", class_="navbox")
        classes = "nowraplinks mw-collapsible navbox-subgroup mw-made-collapsible".split()
        relevant_tables = table.find_all("table", class_=classes)

        race_table, class_table = None, None
        for table in relevant_tables:
            race_table_tmp = table.find(href="/wiki/Race")
            if race_table_tmp is not None:
                race_table = table
                continue
            class_table_tmp = table.find(href="/wiki/Creature_class")
            if class_table_tmp is not None:
                class_table = table
                continue

        if any(table is None for table in (race_table, class_table)):
            raise ValueError("Invalid markup. Cannot find Race/Class tables")

        return race_table, class_table

    @staticmethod
    def _parse_table(table: Tag) -> list[str]:
        lis = table.find_all("li")
        regular_lis = [li for li in lis if ":" not in li.text]
        qualified_lis = [li for li in lis if ":" in li.text]
        regular_types = [a.attrs["title"] for li in regular_lis for a in li.find_all("a")]
        qualified_types = []
        for li in qualified_lis:
            *_, a = li.find_all("a")
            qualified_types.append(a.attrs["title"])

        return sorted([*regular_types, *qualified_types])


_parser = _CreatureTypesParser()
RACES, CLASSES = _parser.races, _parser.classes
