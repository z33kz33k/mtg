"""

    run.py
    ~~~~~~
    Debug run script.

    @author: z33k

"""
from mtgcards.limited import MtgSet, CSV_MAP
from mtgcards.limited import SetParser
from pprint import pprint

mid_parser = SetParser(MtgSet.INNISTRAD_MIDNIGHT_HUNT, CSV_MAP[MtgSet.INNISTRAD_MIDNIGHT_HUNT])
pprint(mid_parser.aggregate_performances)



