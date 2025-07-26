"""

    mtg.mtgwiki
    ~~~~~~~~~~~
    Handle MTG Wiki data.

    @author: z33k

"""
from bs4 import BeautifulSoup
from bs4.element import Tag

from mtg import DATA_DIR
from mtg.utils import from_iterable
from mtg.utils.files import download_file

FILENAME = "creature_type.html"


def download_page() -> None:
    """Download MGT Wiki page on creature types.
    """
    url = "https://mtg.wiki/page/Species"  # (both races and classes are present)
    download_file(url, file_name=FILENAME, dst_dir=DATA_DIR)


class _Parser:
    """Parse MTG Wiki "Species" page for possible races among creature types in a MtG card's type
    line.
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
            download_page()
        self._markup = self.FILEPATH.read_text()
        self._soup = BeautifulSoup(self._markup, "lxml")
        self._races_tag, self._classes_tag = self._get_table_tags()
        self._races = self._parse(self._races_tag)
        self._classes = self._parse(self._classes_tag)

    def _get_table_tags(self) -> tuple[Tag, Tag]:
        # this ensures finding only <table> tags with classes EXACTLY as specified
        tables = self._soup.find_all(
            lambda tag: (
                tag.name == "table" and
                tag.has_attr("class") and
                tag['class'] == ['nowraplinks', 'navbox-subgroup']
            )
        )
        races_tag = from_iterable(
            tables, lambda tag: tag.find("a", string=lambda s: s and s=="Iconic") is not None)
        classes_tag = from_iterable(
            tables, lambda tag: tag.find("a", string=lambda s: s and s=="Spellcasters") is not None)

        if any(tag is None for tag in (races_tag, classes_tag)):
            raise ValueError("Invalid markup. Cannot find Race/Class <table> tags")

        return races_tag, classes_tag


    @staticmethod
    def _parse(table_tag: Tag) -> list[str]:
        li_tags = table_tag.find_all("li")

        regular_li_tags = [li for li in li_tags if ":" not in li.text]
        regular_types = [a.attrs["title"] for li in regular_li_tags for a in li.find_all("a")]

        # didn't really see any such data
        qualified_li_tags = [li for li in li_tags if ":" in li.text]
        qualified_types = []
        for qlt in qualified_li_tags:
            *_, a = qlt.find_all("a")
            qualified_types.append(a.attrs["title"])

        return sorted(
            t.removesuffix(' (creature type)') for t in [*regular_types, *qualified_types])


_parser = _Parser()
RACES, CLASSES = _parser.races, _parser.classes
