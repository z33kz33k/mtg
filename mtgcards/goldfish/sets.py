"""

    mtgcards.goldfish.sets.py
    ~~~~~~~~~~~~~~~~~~~~~~~~~
    Scrape www.mtggoldfish.com for MtG sets data.

    @author: z33k

"""
import json
from enum import Enum
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional

from bs4 import BeautifulSoup
from bs4.element import Tag

from mtgcards.utils import timed_request, Json, OUTPUTDIR, INPUTDIR

DOMAIN = "www.mtggoldfish.com"
URL = f"https://{DOMAIN}/sets/"
DATE_FORMAT = "%b %d, %Y"


class SetFormat(Enum):
    STANDARD = "Standard"
    PIONEER = "Pioneer"
    MODERN = "Modern"


@dataclass(frozen=True)
class SetMetaData:
    name: str
    code: str
    release: Optional[datetime]
    link: str
    format: Optional[SetFormat] = None

    @staticmethod
    def parse_release(datestr: str) -> Optional[datetime]:
        """Parse ``datestr`` of format `Feb 18, 2022` into a datetime object.
        """
        if not datestr:
            return None
        return datetime.strptime(datestr, DATE_FORMAT)

    def as_json(self, format_included=True) -> Json:
        result = {
            "name": self.name,
            "code": self.code,
            "release": self.release.strftime(DATE_FORMAT) if self.release is not None else None,
            "link": self.link,
            "format": self.format,
        }
        if format_included:
            return result
        del result["format"]
        return result

    @classmethod
    def from_json(cls, data: Json) -> "SetMetaData":
        return SetMetaData(data["name"], data["code"], cls.parse_release(data["release"]),
                           data["link"])


def _parse_ul(ul: Tag, set_format: SetFormat) -> SetMetaData:
    *_, name, code, release = ul.find_all("li")
    a = name.find("a")
    name = a.text
    link = a.attrs["href"]
    code = code.find("a").text
    release = SetMetaData.parse_release(release.text[1:-1])
    return SetMetaData(name, code, release, link, set_format)


def scrape(as_json=False) -> Dict[str, List[SetMetaData]]:
    markup = timed_request(URL)
    soup = BeautifulSoup(markup, "lxml")
    divs = soup.find_all("div", class_="sets-format-block")[:3]
    setmap = {}
    for div in divs:
        sets = []
        fmt = SetFormat(div.find("h3").text)
        uls = div.find_all("ul", class_="sets-set-information")
        for ul in uls:
            sets.append(_parse_ul(ul, fmt))
        if as_json:
            setmap[fmt.value] = [st.as_json(format_included=False) for st in sets]
        else:
            setmap[fmt.value] = sets

    return setmap


# TODO: use file utils here (getdir() and so on)
def json_dump(filename="sets_meta.json") -> None:
    dest = OUTPUTDIR / filename
    sets = scrape(as_json=True)
    with dest.open("w", encoding="utf-8") as f:
        json.dump(sets, f, indent=2)


INPUT_METAFILE = INPUTDIR / "sets_meta.json"
if not INPUT_METAFILE.exists():
    raise OSError(f"No sets input meta JSON at {INPUT_METAFILE}.")

with INPUT_METAFILE.open() as f:
    META_SETS_JSON = json.load(f)
STANDARD_META_SETS = [SetMetaData.from_json(meta)
                      for meta in META_SETS_JSON[SetFormat.STANDARD.value]]
PIONEER_META_SETS = [SetMetaData.from_json(meta)
                     for meta in META_SETS_JSON[SetFormat.PIONEER.value]]
MODERN_META_SETS = [SetMetaData.from_json(meta) for meta in META_SETS_JSON[SetFormat.MODERN.value]]


class MtgSet(Enum):
    ALCHEMY = STANDARD_META_SETS[1]

    # Standard as of Q2 2022
    KAMIGAWA_NEON_DYNASTY = STANDARD_META_SETS[0]
    INNISTRAD_CRIMSON_VOW = STANDARD_META_SETS[2]
    INNISTRAD_MIDNIGHT_HUNT = STANDARD_META_SETS[3]
    ADVENTURES_IN_THE_FORGOTTEN_REALMS = STANDARD_META_SETS[4]
    STRIXHAVEN_SCHOOL_OF_MAGES = STANDARD_META_SETS[5]
    # STA is not technically Standard but nevertheless such qualified at www.mtggoldfish.com
    STRIXHAVEN_MYSTICAL_ARCHIVE = STANDARD_META_SETS[6]
    KALDHEIM = STANDARD_META_SETS[7]
    ZENDIKAR_RISING = STANDARD_META_SETS[8]

    # Pioneer as of Q2 2022
    CORE_SET_2021 = PIONEER_META_SETS[0]
    IKORIA_LAIR_OF_BEHEMOTHS = PIONEER_META_SETS[1]
    THEROS_BEYOND_DEATH = PIONEER_META_SETS[2]
    THRONE_OF_ELDRAINE = PIONEER_META_SETS[3]
    CORE_SET_2020 = PIONEER_META_SETS[4]
    WAR_OF_THE_SPARK = PIONEER_META_SETS[5]
    RAVNICA_ALLEGIANCE = PIONEER_META_SETS[6]
    GUILDS_OF_RAVNICA = PIONEER_META_SETS[7]
    CORE_SET_2019 = PIONEER_META_SETS[8]
    DOMINARIA = PIONEER_META_SETS[9]
    RIVALS_OF_IXALAN = PIONEER_META_SETS[10]
    IXALAN = PIONEER_META_SETS[11]
    HOUR_OF_DEVASTATION = PIONEER_META_SETS[12]
    AMONKHET = PIONEER_META_SETS[13]
    MASTERPIECE_SERIES_AMONKHET_INVOCATIONS = PIONEER_META_SETS[14]
    AETHER_REVOLT = PIONEER_META_SETS[15]
    KALADESH = PIONEER_META_SETS[16]
    MASTERPIECE_SERIES_KALADESH_INVENTIONS = PIONEER_META_SETS[17]
    MAGIC_ORIGINS = PIONEER_META_SETS[18]
    MAGIC_2015_CORE_SET = PIONEER_META_SETS[19]
    MAGIC_2014_CORE_SET = PIONEER_META_SETS[20]
    ELDRITCH_MOON = PIONEER_META_SETS[21]
    SHADOWS_OVER_INNISTRAD = PIONEER_META_SETS[22]
    OATH_OF_THE_GATEWATCH = PIONEER_META_SETS[23]
    BATTLE_FOR_ZENDIKAR = PIONEER_META_SETS[24]
    ZENDIKAR_EXPEDITIONS = PIONEER_META_SETS[25]
    DRAGONS_OF_TARKIR = PIONEER_META_SETS[26]
    FATE_REFORGED = PIONEER_META_SETS[27]
    KHANS_OF_TARKIR = PIONEER_META_SETS[28]
    JOURNEY_INTO_NYX = PIONEER_META_SETS[29]
    BORN_OF_THE_GODS = PIONEER_META_SETS[30]
    THEROS = PIONEER_META_SETS[31]
    DRAGONS_MAZE = PIONEER_META_SETS[32]
    GATECRASH = PIONEER_META_SETS[33]
    RETURN_TO_RAVNICA = PIONEER_META_SETS[34]

    # Modern as of Q2 2022
    TIME_SPIRAL_REMASTERED = MODERN_META_SETS[0]
    MODERN_HORIZONS_2 = MODERN_META_SETS[1]
    MODERN_HORIZONS = MODERN_META_SETS[2]
    MODERN_MASTERS_2017_EDITION = MODERN_META_SETS[3]
    MODERN_MASTERS_2015_EDITION = MODERN_META_SETS[4]
    MODERN_EVENT_DECK_2014 = MODERN_META_SETS[5]
    MODERN_MASTERS = MODERN_META_SETS[6]
    MAGIC_2013 = MODERN_META_SETS[7]
    MAGIC_2012 = MODERN_META_SETS[8]
    MAGIC_2011 = MODERN_META_SETS[9]
    MAGIC_2010 = MODERN_META_SETS[10]
    TENTH_EDITION = MODERN_META_SETS[11]
    NINTH_EDITION = MODERN_META_SETS[12]
    EIGHTH_EDITION = MODERN_META_SETS[13]
    AVACYN_RESTORED = MODERN_META_SETS[14]
    DARK_ASCENSION = MODERN_META_SETS[15]
    INNISTRAD = MODERN_META_SETS[16]
    NEW_PHYREXIA = MODERN_META_SETS[17]
    MIRRODIN_BESIEGED = MODERN_META_SETS[18]
    SCARS_OF_MIRRODIN = MODERN_META_SETS[19]
    RISE_OF_THE_ELDRAZI = MODERN_META_SETS[20]
    WORLDWAKE = MODERN_META_SETS[21]
    ZENDIKAR = MODERN_META_SETS[22]
    ALARA_REBORN = MODERN_META_SETS[23]
    CONFLUX = MODERN_META_SETS[24]
    SHARDS_OF_ALARA = MODERN_META_SETS[25]
    EVENTIDE = MODERN_META_SETS[26]
    SHADOWMOOR = MODERN_META_SETS[27]
    MORNINGTIDE = MODERN_META_SETS[28]
    LORWYN = MODERN_META_SETS[29]
    FUTURE_SIGHT = MODERN_META_SETS[30]
    PLANAR_CHAOS = MODERN_META_SETS[31]
    TIME_SPIRAL = MODERN_META_SETS[32]
    TIME_SPIRAL_TIMESHIFTED = MODERN_META_SETS[33]
    COLDSNAP = MODERN_META_SETS[34]
    DISSENSION = MODERN_META_SETS[35]
    GUILDPACT = MODERN_META_SETS[36]
    RAVNICA_CITY_OF_GUILDS = MODERN_META_SETS[37]
    SAVIORS_OF_KAMIGAWA = MODERN_META_SETS[38]
    BETRAYERS_OF_KAMIGAWA = MODERN_META_SETS[39]
    CHAMPIONS_OF_KAMIGAWA = MODERN_META_SETS[40]
    FIFTH_DAWN = MODERN_META_SETS[41]
    DARKSTEEL = MODERN_META_SETS[42]
    MIRRODIN = MODERN_META_SETS[43]

    @staticmethod
    def from_code(code: str) -> "MtgSet":
        mtgset = next((s for s in MtgSet if code == s.value.code), None)
        if mtgset:
            return mtgset
        raise ValueError(f"Cannot match code: {code!r} with any MtG set.")
