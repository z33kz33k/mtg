"""
    mtg.deck.export.py
    ~~~~~~~~~~~~~~~~~~~~
    Export deck data to various file formats (and import it back).

    @author: z33k

"""
import json
import logging
from pathlib import Path

from mtg import OUTPUT_DIR, PathLike
from mtg.deck import Deck, DeckParser, Mode
from mtg.deck.arena import ArenaParser, is_arena_line, is_empty
from mtg.deck.scrapers.cardsrealm import get_source as cardsrealm_get_source
from mtg.deck.scrapers.edhrec import get_source as edhrec_get_source
from mtg.deck.scrapers.melee import get_source as melee_get_source
from mtg.deck.scrapers.mtgarenapro import get_source as mtgarenapro_get_source
from mtg.deck.scrapers.scg import get_source as scg_get_source
from mtg.deck.scrapers.tcgplayer import get_source as tcgplayer_get_source
from mtg.scryfall import Card, aggregate
from mtg.utils import ParsingError
from mtg.utils.json import serialize_dates
from mtg.utils.files import getdir, getfile, sanitize_filename, truncate_path

_log = logging.getLogger(__name__)


def sanitize_source(src: str) -> str:
    src = src.removeprefix("www.")
    if new_src := cardsrealm_get_source(src):
        src = new_src
    elif new_src := edhrec_get_source(src):
        src = new_src
    elif new_src := melee_get_source(src):
        src = new_src
    elif new_src := mtgarenapro_get_source(src):
        src = new_src
    elif new_src := scg_get_source(src):
        src = new_src
    elif new_src := tcgplayer_get_source(src):
        src = new_src
    return src


class Exporter:
    """Export a deck to various text file formats.
    """
    NAME_SEP = "_"
    FORGE_DCK_TEMPLATE = """[metadata]
Name={}
[Commander]
{}
[Main]
{}
[Sideboard]
{}
"""
    FORGE_LINE_TEMPLATE = "{} {}|{}|1"
    FORGE_SIDEBOARD_LINE_TEMPLATE = "SB: {} [{}:{}] {}"
    XMAGE_LINE_TEMPLATE = "{} [{}:{}] {}"
    XMAGE_SIDEBOARD_LINE_TEMPLATE = "SB: {} [{}:{}] {}"

    @property
    def name(self) -> str:
        if self._deck.name:
            return self._normalize_name(self._deck.name).replace(self.NAME_SEP, " ")
        return self._filename_core.replace(self.NAME_SEP, " ")

    def __init__(self, deck: Deck, filename="") -> None:
        """Initialize.

        Args:
            deck: deck to export
            filename: optionally, a custom filename (if not provided a name based on this deck's data and metadata is constructed)
        """
        self._deck = deck
        self._filename_core = self._build_filename_core()
        self._filename = filename or self._build_filename()

    @classmethod
    def _normalize_name(cls, name: str) -> str:
        name = name.replace(" ", cls.NAME_SEP).replace("-", cls.NAME_SEP)
        name = cls.NAME_SEP.join([p.title() for p in name.split(cls.NAME_SEP)])
        name = name.replace(f"5c{cls.NAME_SEP}", f"5C{cls.NAME_SEP}").replace(
            f"4c{cls.NAME_SEP}", f"4C{cls.NAME_SEP}")
        name = name.replace(f"Five{cls.NAME_SEP}Color{cls.NAME_SEP}", f"5C{cls.NAME_SEP}").replace(
            f"Four{cls.NAME_SEP}Color{cls.NAME_SEP}", f"4C{cls.NAME_SEP}")
        return name

    @classmethod
    def _remove_trailing_name_sep(cls, text: str) -> str:
        if text.endswith(cls.NAME_SEP):
            return text[:-len(cls.NAME_SEP)]
        return text

    def _build_filename_core(self) -> str:
        core = ""
        # color
        if len(self._deck.color.value) == 1:
            core += f"Mono{self.NAME_SEP}{self._deck.color.name.title()}{self.NAME_SEP}"
        elif len(self._deck.color.value) == 4:
            core += f"4C{self.NAME_SEP}"
        elif len(self._deck.color.value) == 5:
            core += f"5C{self.NAME_SEP}"
        else:
            core += f"{self._deck.color.name.title()}{self.NAME_SEP}"
        # theme
        if self._deck.theme:
            core += f"{self._deck.theme}{self.NAME_SEP}"
        # archetype
        core += f"{self._deck.archetype.name.title()}{self.NAME_SEP}"
        # set
        if set_code := self._deck.latest_set:
            core += f"{set_code.upper()}{self.NAME_SEP}"
        return self._remove_trailing_name_sep(core)

    def _build_filename(self) -> str:
        name = ""
        # format
        if self._deck.format:
            name += f"{self._deck.format}{self.NAME_SEP}"
        # date
        if date := self._deck.metadata.get("date"):
            date = date.strftime("%Y%m%d")
            name += f"{date}{self.NAME_SEP}{self.NAME_SEP}"
        # prefix (source/author)
        source = sanitize_source(self._deck.source) if self._deck.source else ""
        source = source.replace(".", self.NAME_SEP)
        if self._deck.is_meta_deck and source:
            prefix = source
        else:
            prefix = self._deck.metadata.get("author", "") or source
        name += f"{prefix}{self.NAME_SEP}" if prefix else ""
        # actual name
        if self._deck.name:
            name += f"{self._normalize_name(self._deck.name)}{self.NAME_SEP}"
        # mode
        if mode := self._deck.metadata.get("mode"):
            if mode in {m.value for m in Mode}:
                name += f"{mode}{self.NAME_SEP}"
        # core:
        core = self._filename_core
        core = f"({core})" if name else core
        name += f"{core}{self.NAME_SEP}"
        # meta
        if self._deck.is_meta_deck:
            name += f"Meta{self.NAME_SEP}"
            meta = self._deck.metadata["meta"]
            if meta_place := meta.get("place"):
                name += f"#{str(meta_place).zfill(2)}{self.NAME_SEP}"
        # event
        event_name = self._deck.metadata.get("event_name", "") or self._deck.metadata.get(
            "event", {})
        if event_name and isinstance(event_name, dict):
            event_name = event_name.get("name", "")
        if event_name and not self._deck.is_meta_deck:
            name += f"Event{self.NAME_SEP}{event_name}{self.NAME_SEP}"
        return sanitize_filename(self._remove_trailing_name_sep(name))

    def to_arena(self, dstdir: PathLike = "", extended=True) -> None:
        """Export deck to a MTGA deckfile text format (as a .txt file).

        Args:
            dstdir: optionally, the destination directory (if not provided CWD is used)
            extended: optionally, include the card's set and collector number (default: True)
        """
        dstdir = dstdir or OUTPUT_DIR / "arena"
        dstdir = getdir(dstdir)
        dst = dstdir / f"{self._filename}.txt"
        dst = Path(truncate_path(str(dst)))
        _log.info(f"Exporting deck to: '{dst}'...")
        dst.write_text(
            self._deck.decklist_extended if extended else self._deck.decklist, encoding="utf-8")

    def to_json(self, dstdir: PathLike = "", extended=True) -> None:
        """Export deck to a .json file.

        JSON exported to file holds the whole decklist (in regular or extended format) and not only
        IDs.

        Args:
            dstdir: optionally, the destination directory (if not provided CWD is used)
            extended: optionally, include in decklist the card's set and collector number (default: True)
        """
        data = {
            "metadata": self._deck.metadata,
            "decklist": self._deck.decklist_extended if extended else self._deck.decklist,
        }
        data = json.dumps(data, indent=4, ensure_ascii=False, default=serialize_dates)
        dstdir = dstdir or OUTPUT_DIR / "json"
        dstdir = getdir(dstdir)
        dst = dstdir / f"{self._filename}.json"
        dst = Path(truncate_path(str(dst)))
        _log.info(f"Exporting deck to: '{dst}'...")
        dst.write_text(data, encoding="utf-8")

    @classmethod
    def _to_forge_line(cls, playset: list[Card]) -> str:
        card = playset[0]
        return cls.FORGE_DCK_TEMPLATE.format(len(playset), card.first_face_name, card.set.upper())

    def _build_forge(self) -> str:
        commander = [
            self._to_forge_line(playset) for playset in
            aggregate(self._deck.commander).values()] if self._deck.commander else []
        if self._deck.partner_commander:
            commander += [self._to_forge_line(playset) for playset in aggregate(
                self._deck.partner_commander).values()]
        maindeck = [
            self._to_forge_line(playset) for playset in aggregate(*self._deck.maindeck).values()]
        sideboard = [
            self._to_forge_line(playset) for playset in
            aggregate(*self._deck.sideboard).values()] if self._deck.sideboard else []
        return self.FORGE_DCK_TEMPLATE.format(
            self.name, "\n".join(commander), "\n".join(maindeck), "\n".join(sideboard))

    def to_forge(self, dstdir: PathLike = "") -> None:
        """Export deck to a Forge MTG deckfile format (.dck).

        Args:
            dstdir: optionally, the destination directory (if not provided CWD is used)
        """
        dstdir = dstdir or OUTPUT_DIR / "dck"
        dstdir = getdir(dstdir)
        dst = dstdir / f"{self._filename}.dck"
        dst = Path(truncate_path(str(dst)))
        _log.info(f"Exporting deck to: '{dst}'...")
        dst.write_text(self._build_forge(), encoding="utf-8")

    @classmethod
    def _to_xmage_line(cls, playset: list[Card], sideboard=False) -> str:
        card = playset[0]
        template = cls.XMAGE_SIDEBOARD_LINE_TEMPLATE if sideboard else cls.XMAGE_LINE_TEMPLATE
        return template.format(
            len(playset), card.set.upper(), card.collector_number, card.first_face_name)

    def _get_xmage_metadata_lines(self) -> list[str]:
        lines = [f"NAME:{self.name}"]
        if self._deck.format:
            lines += [f"FORMAT:{self._deck.format}"]
        if author :=self._deck.metadata.get("author"):
            lines += [f"AUTHOR:{author}"]
        if date := self._deck.metadata.get("date"):
            lines += [f"DATE:{date}"]
        if source := sanitize_source(self._deck.source) if self._deck.source else "":
            lines += [f"SOURCE:{source}"]
        if url := self._deck.metadata.get("video_url") or self._deck.metadata.get("url"):
            lines += [f"URL:{url}"]
        return lines

    def _build_xmage(self) -> str:
        lines = self._get_xmage_metadata_lines()
        lines += [
            self._to_xmage_line(playset) for playset in aggregate(*self._deck.maindeck).values()]
        commander = [
            self._to_xmage_line(playset, sideboard=True) for playset in
            aggregate(self._deck.commander).values()] if self._deck.commander else []
        if self._deck.partner_commander:
            commander += [self._to_xmage_line(playset, sideboard=True) for playset in aggregate(
                self._deck.partner_commander).values()]
        if commander:
            lines += commander
        else:
            lines += [
                self._to_xmage_line(playset, sideboard=True) for playset in
                aggregate(*self._deck.sideboard).values()] if self._deck.sideboard else []
        return "\n".join(lines)

    def to_xmage(self, dstdir: PathLike = "") -> None:
        """Export deck to a XMage deckfile format (.dck).

        Args:
            dstdir: optionally, the destination directory (if not provided CWD is used)
        """
        dstdir = dstdir or OUTPUT_DIR / "dck"
        dstdir = getdir(dstdir)
        dst = dstdir / f"{self._filename}.dck"
        dst = Path(truncate_path(str(dst)))
        _log.info(f"Exporting deck to: '{dst}'...")
        dst.write_text(self._build_xmage(), encoding="utf-8")


def from_arena(path: PathLike) -> Deck:
    """Import deck from a MTG Arena deckfile format (.txt).

    Args:
        path: path to an Arena deck file
    """
    file = getfile(path, ext=".txt")
    decklist = file.read_text(encoding="utf-8")
    if not all(is_arena_line(l) or is_empty(l) for l in decklist.splitlines()):
        raise ValueError(f"Not an MTG Arena deck file: '{file}'")
    return ArenaParser(decklist).parse(suppressed_errors=())


def _parse_forge_line(line: str) -> list[Card]:
    quantity, rest = line.split(maxsplit=1)
    name, _, _ = rest.split("|")
    return DeckParser.get_playset(DeckParser.find_card(name), int(quantity))


def from_forge(path: PathLike) -> Deck:
    """Import a deck from a Forge MTG deckfile format (.dck).

    Args:
        path: path to a .dck file
    """
    file = getfile(path, ext=".dck")
    commander, maindeck, sideboard, metadata = None, [], [], {}
    commander_on, maindeck_on, sideboard_on = False, False, False
    for line in file.read_text(encoding="utf-8").splitlines():
        if line.startswith("Name="):
            metadata = {"name": (line.removeprefix("Name="))}
            # TODO: handle other metadata
        elif line == "[Commander]":
            commander_on = True
            continue
        elif line == "[Main]":
            commander_on, maindeck_on = False, True
            continue
        elif line == "[Sideboard]":
            maindeck_on, sideboard_on = False, True
            continue
        elif not line:
            continue

        if commander_on:
            commander = _parse_forge_line(line)[0]
        elif maindeck_on:
            maindeck += _parse_forge_line(line)
        elif sideboard_on:
            sideboard += _parse_forge_line(line)

    deck = Deck(maindeck, sideboard, commander, metadata=metadata)
    if not deck:
        raise ParsingError(f"Unable to parse '{path}' into a deck")
    return deck
