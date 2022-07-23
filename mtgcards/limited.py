"""

    mtgcards.limited.py
    ~~~~~~~~~~~~~~~~~~~
    Limited calculations.

    @author: z33k

"""
import csv
from enum import Enum
from pathlib import Path
from typing import List, Optional, Tuple

from mtgcards.goldfish.cards import Mana
from mtgcards.goldfish.sets import MtgSet


CSV_MAP = {
    MtgSet.ZENDIKAR_RISING: Path("mtgcards/data/seventeen_data/zendikar_rising.csv"),
    MtgSet.KALDHEIM: Path("mtgcards/data/seventeen_data/kaldheim.csv"),
    MtgSet.STRIXHAVEN_SCHOOL_OF_MAGES: Path("mtgcards/data/seventeen_data/strixhaven.csv"),
    MtgSet.ADVENTURES_IN_THE_FORGOTTEN_REALMS: Path(
        "mtgcards/data/seventeen_data/adventures_forgotten_realms.csv"),
    MtgSet.INNISTRAD_MIDNIGHT_HUNT: Path("mtgcards/data/seventeen_data/midnight_hunt.csv"),
    MtgSet.INNISTRAD_CRIMSON_VOW: Path("mtgcards/data/seventeen_data/crimson_vow.csv"),
    MtgSet.KAMIGAWA_NEON_DYNASTY: Path("mtgcards/data/seventeen_data/neon_dynasty.csv"),
    MtgSet.STREETS_OF_NEW_CAPENNA: Path("mtgcards/data/seventeen_data/streets_new_capenna.csv"),
}


class Color(Enum):
    """Enumeration of MtG colors played in Limited as classified in 17lands.com data.
    """
    MONO_WHITE = "Mono-White"
    MONO_BLUE = "Mono-Blue"
    MONO_BLACK = "Mono-Black"
    MONO_RED = "Mono-Red"
    MONO_GREEN = "Mono-Green"
    MONO_WHITE_WITH_SPLASH = "Mono-White + Splash"
    MONO_BLUE_WITH_SPLASH = "Mono-Blue + Splash"
    MONO_BLACK_WITH_SPLASH = "Mono-Black + Splash"
    MONO_RED_WITH_SPLASH = "Mono-Red + Splash"
    MONO_GREEN_WITH_SPLASH = "Mono-Green + Splash"
    AZORIUS = "Azorius (WU)"
    DIMIR = "Dimir (UB)"
    RAKDOS = "Rakdos (BR)"
    GRUUL = "Gruul (RG)"
    SELESNYA = "Selesnya (GW)"
    ORZHOV = "Orzhov (WB)"
    GOLGARI = "Golgari (BG)"
    SIMIC = "Simic (GU)"
    IZZET = "Izzet (UR)"
    BOROS = "Boros (RW)"
    AZORIUS_WITH_SPLASH = "Azorius (WU) + Splash"
    DIMIR_WITH_SPLASH = "Dimir (UB) + Splash"
    RAKDOS_WITH_SPLASH = "Rakdos (BR) + Splash"
    GRUUL_WITH_SPLASH = "Gruul (RG) + Splash"
    SELESNYA_WITH_SPLASH = "Selesnya (GW) + Splash"
    ORZHOV_WITH_SPLASH = "Orzhov (WB) + Splash"
    GOLGARI_WITH_SPLASH = "Golgari (BG) + Splash"
    SIMIC_WITH_SPLASH = "Simic (GU) + Splash"
    IZZET_WITH_SPLASH = "Izzet (UR) + Splash"
    BOROS_WITH_SPLASH = "Boros (RW) + Splash"
    JESKAI = "Jeskai (WUR)"
    SULTAI = "Sultai (UBG)"
    MARDU = "Mardu (BRW)"
    TEMUR = "Temur (RGU)"
    ABZAN = "Abzan (GWB)"
    ESPER = "Esper (WUB)"
    GRIXIS = "Grixis (UBR)"
    JUND = "Jund (BRG)"
    NAYA = "Naya (RGW)"
    BANT = "Bant (GWU)"

    @classmethod
    def to_mana(cls, color: "Color") -> Tuple[Mana, ...]:
        if color is cls.MONO_WHITE:
            return Mana.WHITE,
        elif color is cls.MONO_BLUE:
            return Mana.BLUE,
        elif color is cls.MONO_BLACK:
            return Mana.BLACK,
        elif color is cls.MONO_RED:
            return Mana.RED,
        elif color is cls.MONO_GREEN:
            return Mana.GREEN,
        elif color is cls.MONO_WHITE_WITH_SPLASH:
            return Mana.WHITE, Mana.COLORLESS
        elif color is cls.MONO_BLUE_WITH_SPLASH:
            return Mana.BLUE, Mana.COLORLESS
        elif color is cls.MONO_BLACK_WITH_SPLASH:
            return Mana.BLACK, Mana.COLORLESS
        elif color is cls.MONO_RED_WITH_SPLASH:
            return Mana.RED, Mana.COLORLESS
        elif color is cls.MONO_GREEN_WITH_SPLASH:
            return Mana.GREEN, Mana.COLORLESS
        elif color is cls.AZORIUS:
            return Mana.WHITE, Mana.BLUE
        elif color is cls.DIMIR:
            return Mana.BLUE, Mana.BLACK
        elif color is cls.RAKDOS:
            return Mana.BLACK, Mana.RED
        elif color is cls.GRUUL:
            return Mana.RED, Mana.GREEN
        elif color is cls.SELESNYA:
            return Mana.GREEN, Mana.WHITE
        elif color is cls.ORZHOV:
            return Mana.WHITE, Mana.BLACK
        elif color is cls.GOLGARI:
            return Mana.BLACK, Mana.GREEN
        elif color is cls.SIMIC:
            return Mana.GREEN, Mana.BLUE
        elif color is cls.IZZET:
            return Mana.BLUE, Mana.RED
        elif color is cls.BOROS:
            return Mana.RED, Mana.WHITE
        elif color is cls.AZORIUS_WITH_SPLASH:
            return Mana.WHITE, Mana.BLUE, Mana.COLORLESS
        elif color is cls.DIMIR_WITH_SPLASH:
            return Mana.BLUE, Mana.BLACK, Mana.COLORLESS
        elif color is cls.RAKDOS_WITH_SPLASH:
            return Mana.BLACK, Mana.RED, Mana.COLORLESS
        elif color is cls.GRUUL_WITH_SPLASH:
            return Mana.RED, Mana.GREEN, Mana.COLORLESS
        elif color is cls.SELESNYA_WITH_SPLASH:
            return Mana.GREEN, Mana.WHITE, Mana.COLORLESS
        elif color is cls.ORZHOV_WITH_SPLASH:
            return Mana.WHITE, Mana.BLACK, Mana.COLORLESS
        elif color is cls.GOLGARI_WITH_SPLASH:
            return Mana.BLACK, Mana.GREEN, Mana.COLORLESS
        elif color is cls.SIMIC_WITH_SPLASH:
            return Mana.GREEN, Mana.BLUE, Mana.COLORLESS
        elif color is cls.IZZET_WITH_SPLASH:
            return Mana.BLUE, Mana.RED, Mana.COLORLESS
        elif color is cls.BOROS_WITH_SPLASH:
            return Mana.RED, Mana.WHITE, Mana.COLORLESS
        elif color is cls.JESKAI:
            return Mana.BLUE, Mana.RED, Mana.WHITE
        elif color is cls.SULTAI:
            return Mana.BLACK, Mana.GREEN, Mana.BLUE
        elif color is cls.MARDU:
            return Mana.RED, Mana.WHITE, Mana.BLACK
        elif color is cls.TEMUR:
            return Mana.GREEN, Mana.BLUE, Mana.RED
        elif color is cls.ABZAN:
            return Mana.WHITE, Mana.BLACK, Mana.GREEN
        elif color is cls.ESPER:
            return Mana.WHITE, Mana.BLUE, Mana.BLACK
        elif color is cls.GRIXIS:
            return Mana.BLUE, Mana.BLACK, Mana.RED
        elif color is cls.JUND:
            return Mana.BLACK, Mana.RED, Mana.GREEN
        elif color is cls.NAYA:
            return Mana.RED, Mana.GREEN, Mana.WHITE
        elif color is cls.BANT:
            return Mana.GREEN, Mana.WHITE, Mana.BLUE
        else:
            raise ValueError(f"Invalid color: {color}.")


class Performance:
    """Draft color performance according to 17lands.com data.
    """
    def __init__(self, color: Color, wins: int, games: int,
                 mtgset: Optional[MtgSet] = None) -> None:
        self._color = color
        self._wins, self._games = wins, games
        self.__mtgset = mtgset

    @property
    def color(self) -> Color:
        return self._color

    @property
    def wins(self) -> int:
        return self._wins

    @property
    def games(self) -> int:
        return self._games

    @property
    def winrate(self) -> float:
        return self.wins * 100 / self.games if self.games else 0.0

    @property
    def winrate_str(self) -> str:
        return f"{self.winrate:.2f}%"

    @property
    def mtgset(self) -> MtgSet:
        return self.__mtgset

    @mtgset.setter
    def mtgset(self, value: Optional[MtgSet]) -> None:
        self.__mtgset = value

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self.color}, winrate={self.winrate_str})"


class SetParser:
    """Parser of set performance 17lands.com data.
    """
    def __init__(self, mtgset: MtgSet, csv_path: Path) -> None:
        self._mtgset, self._csv_path = mtgset, csv_path
        self._performances = self._parse()

    @property
    def mtgset(self) -> MtgSet:
        return self._mtgset

    @property
    def csv_path(self) -> Path:
        return self._csv_path

    def _parse(self) -> List[Performance]:
        perfs = []
        with self.csv_path.open(newline="") as f:
            for row in csv.reader(f):
                perfs.append(Performance(Color(row[0]), int(row[1]), int(row[2])))
        return perfs

    @property
    def performances(self) -> List[Performance]:
        return self._performances

    @property
    def sorted_performances(self) -> List[Performance]:
        return sorted(self.performances, key=lambda p: p.winrate, reverse=True)

