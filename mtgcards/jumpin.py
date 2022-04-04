"""

    mtgcards.jumpin.py
    ~~~~~~~~~~~~~~~~~~
    Scrape official WotC JumpIn! page for decks data.

    @author: z33k

"""
URL = "https://magic.wizards.com/en/articles/archive/magic-digital/innistrad-crimson-vow-jump-" \
      "event-details-and-packets-2021-11-10"

# from mtgcards.utils import timed_request
# from mtgcards.jumpin import URL
# markup = timed_request(URL)
# from bs4 import BeautifulSoup
# soup = BeautifulSoup(markup, "lxml")
# decklists = soup.find_all("div", class_="page-width bean_block bean_block_deck_list bean--wiz-content-deck-list clearfix")
# tables = soup.find_all("table", class_="responsive-table large-only")
# soup = BeautifulSoup(markup, "lxml")
# tables = soup.find_all("table", class_="responsive-table large-only")
# tables = soup.find_all("div", class_="rankings-table with-scroll")
# from pathlib import Path
# temp = Path("output/temp.html")
# temp.write_text(str(soup))
# 2402477
# tables = soup.find_all("table", cellspacing="0", cellpadding="0", border="0")