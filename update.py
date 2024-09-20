"""

    update.py
    ~~~~~~~~~
    Script to download updated data files and update the README.

    @author: z33k

"""
from mtgcards.scryfall import download_scryfall_bulk_data, download_scryfall_set_data
from mtgcards.mtgwiki import download_creature_type_page
from mtgcards.yt import update_readme_with_deck_data


if __name__ == '__main__':
    download_creature_type_page()
    download_scryfall_bulk_data()
    download_scryfall_set_data()
    update_readme_with_deck_data()
