"""

    update.py
    ~~~~~~~~~
    Script to download updated data files.

    @author: z33k

"""
from mtgcards.scryfall import download_scryfall_bulk_data, download_scryfall_set_data
from mtgcards.mtgwiki import download_creature_type_page


if __name__ == '__main__':
    download_creature_type_page()
    download_scryfall_bulk_data()
    download_scryfall_set_data()



