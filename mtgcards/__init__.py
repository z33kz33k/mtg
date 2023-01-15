"""

    mtgcards
    ~~~~~~~~
    Root package.

    @author: z33k

"""
__appname__ = __name__
__version__ = "0.3.6"
__description__ = "Scrape data on MtG cards and do other stuff."
__author__ = "z33k"
__license__ = "MIT License"

from mtgcards.utils.log import rootlogger
from mtgcards.const import OUTPUTDIR

from mtgcards.scryfall import Card

log = rootlogger(__name__, OUTPUTDIR)


