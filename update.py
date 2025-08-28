"""

    update.py
    ~~~~~~~~~
    Script to download updated data files and update the README.

    @author: z33k

"""
from mtg.scryfall import download_scryfall_bulk_data, download_scryfall_set_data
from mtg.mtgwiki import download_page as download_wiki_page
from mtg.yt.data import update_readme_with_deck_data

if __name__ == '__main__':
    download_wiki_page()
    download_scryfall_bulk_data()
    download_scryfall_set_data()
    update_readme_with_deck_data()
