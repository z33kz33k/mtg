"""
    mtg.deck.export.py
    ~~~~~~~~~~~~~~~~~~~~
    Export deck data to various formats.

    @author: z33k

"""
import json
import logging

from mtg import Json, OUTPUT_DIR, PathLike
from mtg.deck import Deck, DeckParser, Mode
from mtg.deck.arena import ArenaParser, is_arena_line, is_empty
from mtg.scryfall import Card, aggregate
from mtg.utils import ParsingError, extract_int, from_iterable, serialize_dates
from mtg.utils.files import getdir, getfile

_log = logging.getLogger(__name__)


# TODO: In case of Forge, stop using filename to encode deck metadata as Forge format can handle
#  metadata
class Exporter:
    """Export a deck to various text file formats. Also, import a deck from those formats.
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
    # TODO: overhaul this
    SOURCE_NICKNAMES = {
        "aetherhub.com": "Aetherhub",
        "archidekt.com": "Archidekt",
        'decks.tcgplayer.com': "TCGplayer",
        'deckstats.net': "Deckstats",
        'flexslot.gg': "Flexslot",
        'infinite.tcgplayer.com': "TCGplayer",
        'manastack.com': "Manastack",
        "melee.gg": "MeleeGG",
        'moxfield.com': "Moxfield",
        "mtg.cardsrealm.com": "Cardsrealm",
        "mtga.untapped.gg": "Untapped",
        "mtgarena.pro": "MGTArenaPro",
        "mtgazone.com": "MGTAZone",
        'mtgdecks.net': "MTGDecks",
        'mtgmelee.com': "MeleeGG",
        'mtgtop8.com': "MTGTop8",
        'old.starcitygames.com': "Starcity",
        'pennydreadfulmagic.com': "PDMagic",
        'scryfall.com': "Scryfall",
        "tappedout.net": "TappedOut",
        'www.archidekt.com': "Archidekt",
        "www.cardhoarder.com": "Cardhoarder",
        "www.hareruya.com": "Hareruya",
        'www.manatraders.com': "Manatraders",
        'www.moxfield.com': "Moxfield",
        'www.mtggoldfish.com': "Goldfish",
        'www.mtgotraders.com': "MTGOTraders",
        'www.mtgtop8.com': "MTGTop8",
        'www.streamdecker.com': "Streamdecker",
        'www.topdecked.com': "TopDecked",
    }
    FMT_NICKNAMES = {
        'alchemy': "Alh",
        'brawl': "Bwl",
        'commander': "Cmd",
        'duel': "Dl",
        'explorer': "Exp",
        'future': "Ftr",
        'gladiator': "Gld",
        'historic': "Hst",
        'legacy': "Lgc",
        'modern': "Mdn",
        'oathbreaker': "Oth",
        'oldschool': "Old",
        'pauper': "Ppr",
        'paupercommander': "PprCmd",
        'penny': "Pnn",
        'pioneer': "Pnr",
        'predh': "Pdh",
        'premodern': "PreMdn",
        'standard': "Std",
        'standardbrawl': "StdBwl",
        'timeless': "Tml",
        'vintage': "Vnt",
    }

    def __init__(self, deck: Deck, filename="") -> None:
        """Initialize.

        Args:
            deck: deck to export
            filename: optionally, a custom filename (if not provided a name based on this deck's data and metadata is constructed)
        """
        self._deck = deck
        self._filename = filename or self._build_filename()

    @classmethod
    def _normalize(cls, name: str) -> str:
        name = name.replace(" ", cls.NAME_SEP).replace("-", cls.NAME_SEP)
        name = cls.NAME_SEP.join([p.title() for p in name.split(cls.NAME_SEP)])
        name = name.replace(f"5c{cls.NAME_SEP}", f"5C{cls.NAME_SEP}").replace(
            f"4c{cls.NAME_SEP}", f"4C{cls.NAME_SEP}")
        name = name.replace(f"Five{cls.NAME_SEP}Color{cls.NAME_SEP}", f"5C{cls.NAME_SEP}").replace(
            f"Four{cls.NAME_SEP}Color{cls.NAME_SEP}", f"4C{cls.NAME_SEP}")
        return name

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
        return core

    def _build_filename(self) -> str:
        # prefix (source/author)
        source = self.SOURCE_NICKNAMES.get(self._deck.source) or ""
        prefix = source if self._deck.is_meta_deck and source else self._deck.metadata.get(
            "author", "")
        name = f"{prefix}{self.NAME_SEP}" if prefix else ""
        # format
        if self._deck.format:
            name += f"{self.FMT_NICKNAMES[self._deck.format.lower()]}{self.NAME_SEP}"
        # mode
        if mode := self._deck.metadata.get("mode"):
            if mode in {m.value for m in Mode}:
                name += f"{mode}{self.NAME_SEP}"
        # meta
        if self._deck.is_meta_deck:
            name += f"Meta{self.NAME_SEP}"
            meta = self._deck.metadata["meta"]
            if meta_place := meta.get("place"):
                name += f"#{str(meta_place).zfill(2)}{self.NAME_SEP}"
        if self._deck.name:
            name += f"{self._normalize(self._deck.name)}{self.NAME_SEP}"
        else:
            name += self._build_filename_core()
        # set
        if set_code := self._deck.latest_set:
            name += set_code.upper()
        return name

    @staticmethod
    def _to_forge_line(playset: list[Card]) -> str:
        card = playset[0]
        return f"{len(playset)} {card.first_face_name}|{card.set.upper()}|1"

    # TODO: stop using filename to encode deck metadata (see use of self._parse_filename())
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
            self._filename, "\n".join(commander), "\n".join(maindeck), "\n".join(sideboard))

    def to_forge(self, dstdir: PathLike = "") -> None:
        """Export deck to a Forge MTG deckfile format (.dck).

        Args:
            dstdir: optionally, the destination directory (if not provided CWD is used)
        """
        dstdir = dstdir or OUTPUT_DIR / "dck"
        dstdir = getdir(dstdir)
        dst = dstdir / f"{self._filename}.dck"
        _log.info(f"Exporting deck to: '{dst}'...")
        dst.write_text(self._build_forge(), encoding="utf-8")

    @classmethod
    def _parse_filename(cls, name: str) -> Json:
        metadata = {}
        nameparts = name.split(cls.NAME_SEP)
        if src := from_iterable(
                cls.SOURCE_NICKNAMES,
                lambda s: any(np == cls.SOURCE_NICKNAMES[s] for np in nameparts)):
            metadata["source"] = src
            nameparts.remove(cls.SOURCE_NICKNAMES[src])
        if fmt := from_iterable(
                cls.FMT_NICKNAMES,
                lambda f: any(np == cls.FMT_NICKNAMES[f] for np in nameparts)):
            metadata["format"] = fmt
            nameparts.remove(cls.FMT_NICKNAMES[fmt])
        if mode := from_iterable(
                {m.value for m in Mode}, lambda mode: any(np == mode for np in nameparts)):
            metadata["mode"] = mode
            nameparts.remove(mode)
        try:
            idx = nameparts.index(f"Meta")
        except ValueError:
            idx = -1
        if idx != -1:
            idx += 1
            metadata["meta"] = {}
            metadata["meta"]["place"] = extract_int(nameparts[idx])
            del nameparts[idx]
            nameparts.remove(f"Meta")
        metadata["name"] = " ".join(nameparts[:-1])
        return metadata

    @staticmethod
    def _parse_forge_line(line: str) -> list[Card]:
        quantity, rest = line.split(maxsplit=1)
        name, _, _ = rest.split("|")
        return DeckParser.get_playset(DeckParser.find_card(name), int(quantity))

    @classmethod
    def from_forge(cls, path: PathLike) -> Deck:
        """Import a deck from a Forge MTG deckfile format (.dck).

        Args:
            path: path to a .dck file
        """
        file = getfile(path, ext=".dck")
        commander, maindeck, sideboard, metadata = None, [], [], {}
        commander_on, maindeck_on, sideboard_on = False, False, False
        for line in file.read_text(encoding="utf-8").splitlines():
            if line.startswith("Name="):
                metadata = cls._parse_filename(line.removeprefix("Name="))
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
                commander = cls._parse_forge_line(line)[0]
            elif maindeck_on:
                maindeck += cls._parse_forge_line(line)
            elif sideboard_on:
                sideboard += cls._parse_forge_line(line)

        deck = Deck(maindeck, sideboard, commander, metadata=metadata)
        if not deck:
            raise ParsingError(f"Unable to parse '{path}' into a deck")
        return deck

    def to_arena(self, dstdir: PathLike = "", extended=True) -> None:
        """Export deck to a MTGA deckfile text format (as a .txt file).

        Args:
            dstdir: optionally, the destination directory (if not provided CWD is used)
            extended: optionally, include the card's set and collector number (default: True)
        """
        dstdir = dstdir or OUTPUT_DIR / "arena"
        dstdir = getdir(dstdir)
        dst = dstdir / f"{self._filename}.txt"
        _log.info(f"Exporting deck to: '{dst}'...")
        dst.write_text(
            self._deck.decklist_extended if extended else self._deck.decklist, encoding="utf-8")

    @classmethod
    def from_arena(cls, path: PathLike) -> Deck:
        """Import deck from a MTG Arena deckfile format (.txt).

        Args:
            path: path to an Arena deck file
        """
        file = getfile(path, ext=".txt")
        lines = file.read_text(encoding="utf-8").splitlines()
        if not all(is_arena_line(l) or is_empty(l) for l in lines):
            raise ValueError(f"Not an MTG Arena deck file: '{file}'")
        metadata = cls._parse_filename(file.name)
        deck = ArenaParser(lines, metadata).parse(
            suppress_parsing_errors=False, suppress_invalid_deck=False)
        if not deck:
            raise ParsingError(f"Unable to parse '{path}' into a deck")
        return deck

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
        _log.info(f"Exporting deck to: '{dst}'...")
        dst.write_text(data, encoding="utf-8")
