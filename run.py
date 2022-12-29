"""

    run.py
    ~~~~~~
    Debug run script.

    @author: z33k

"""
import json
from pathlib import Path
from mtgcards.scryfall import arena_cards, find_by_parts, format_cards, DATADIR, FILENAME, Card, \
    TypeLine
from mtgcards.utils.files import getdir
from mtgcards.utils import from_iterable

arena_cards = arena_cards()
historic_cards = format_cards("historic", arena_cards)
alchemy_rebalanced = {card for card in historic_cards if card.is_alchemy_rebalance}
alchemy_originals = {card.alchemy_rebalance_original for card in alchemy_rebalanced}




