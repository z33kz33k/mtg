"""

    mtgcards
    ~~~~~~~~
    Root package.

    @author: z33k

"""
from enum import Enum
from typing import Any, Dict


__version__ = "0.1.1"

Json = Dict[str, Any]


class MtgSet(Enum):
    ALCHEMY = "Y22"
    # Standard as of Q2 2022
    ZENDIKAR_RISING = "ZNR"
    KALDHEIM = "KHM"
    STRIXHAVEN_MYSTICAL_ARCHIVE = "STA"
    STRIXHAVEN_SCHOOL_OF_MAGES = "STX"
    ADVENTURES_IN_THE_FORGOTTEN_REALMS = "AFR"
    INNISTRAD_MIDNIGHT_HUNT = "MID"
    INNISTRAD_CRIMSON_VOW = "VOW"
    KAMIGAWA_NEON_DYNASTY = "NEO"
    # Non-Standard as of Q2 2022




