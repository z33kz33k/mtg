# mtgcards
Do something with MTG cards data.

### Description

This is a hobby project.

It started as a card data scraping from `MTG Goldfish`. Then, some JumpIn! packets info scraping 
was added. Then, there was some play with Limited data from `17lands.com` when I thought I had to 
bear with utter boringness of that format (before the dawn of Golden Packs on Arena). Then, I 
discovered I don't need to scrape anything because `Scryfall`.

Then, I quit.

Now, the main focus is `decks` and `yt` packages (parsing data on youtubers' decks from YT videos 
descriptions).

### What works

* Scryfall data management via downloading bulk data with `scrython` and wrapping it in convenient 
  abstractions
* Scraping YT channels for videos with decklists in descriptions (using no less than three Python 
  libraries: `scrapetube`, `pytubefix`, and `youtubesearchpython` to avoid bothering with Google 
  APIs)
* Arena, Goldfish, Moxfield and Aetherhub deck parsers work, so:
    * Arena decklists pasted into video descriptions are parsed into Deck objects
    * Goldfish and Moxfield links contained in those descriptions are parsed into Deck objects
    * Those above work even if they are behind shortener links and need unshortening first
    * Arena decklists in links to pastebin-like services (like Amazonian does) work too
* Other decklist services are in plans
* Scraping Goldfish for meta-decks
* Exporting decks into a Forge MTG .dck format or Arena decklist saved into a .txt file - with 
  autogenerated, descriptive names based on scraped deck's metadata
* Importing back into a Deck from those formats




