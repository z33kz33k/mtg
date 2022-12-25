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

# arena_cards = arena_cards()
# standard_arena_cards = format_cards("standard", arena_cards)
# explorer_arena_cards = format_cards("explorer", arena_cards)
# valki = find_by_parts("valki god lies".split(), explorer_arena_cards)

valki_id = 'ea7e4c65-b4c4-4795-9475-3cba71c50ea5'

source = getdir(DATADIR) / FILENAME
with source.open() as f:
    data = json.load(f)

valki_data = from_iterable(data, lambda d: d["id"] == valki_id)

tl = TypeLine(valki_data["card_faces"][0]["type_line"])
print(tl)
tl2 = TypeLine(valki_data["card_faces"][1]["type_line"])
print(tl2)
valki = Card(valki_data)
print(valki)




