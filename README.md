# mtgcards
Do something with MTG cards data.

### Description

This is a hobby project.

It started as a card data scraping from `MTG Goldfish`. Then, some JumpIn! packets info scraping 
was added. Then, there was some play with Limited data from `17lands.com` when I thought I had to 
bear with utter boringness of that format (before the dawn of Golden Packs on Arena) [_This part 
has been deprecated and moved to `archive` package_]. Then, I discovered I don't need to scrape 
anything because [Scryfall](https://scryfall.com).

Then, I quit (Arena).

Now, the main focus is `decks` package and `yt` module (parsing data on youtubers' decks from YT videos 
descriptions).

### What works

* Scryfall data management via downloading bulk data with 
  [scrython](https://github.com/NandaScott/Scrython) and wrapping it in convenient abstractions
* Scraping YT channels for videos with decklists in descriptions (using no less than three Python 
  libraries: [scrapetube](https://github.com/dermasmid/scrapetube), 
  [pytubefix](https://github.com/JuanBindez/pytubefix), and 
  [youtubesearchpython](https://github.com/alexmercerind/youtube-search-python) to avoid bothering 
  with Google APIs)
* Arena, [Goldfish](https://www.mtggoldfish.com), [Moxfield](https://www.moxfield.com), 
  [Aetherhub](https://aetherhub.com), [Streamdecker](https://www.streamdecker.com/landing) 
  and [Untapped](https://mtga.untapped.gg) deck parsers work, so:
    * Arena decklists pasted into video descriptions are parsed into Deck objects
    * Goldfish, Moxfield, Aetherhub, Streamdecker and Untapped links contained in those 
      descriptions are parsed into Deck objects
    * Due to its dynamic nature, Untapped is scraped using 
      [Selenium](https://github.com/SeleniumHQ/Selenium)
    * Both Untapped decklist types featured in YT videos are supported: regular deck and profile deck
    * Those above work even if they are behind shortener links and need unshortening first
    * Arena decklists in links to pastebin-like services (like 
      [Amazonian](https://www.youtube.com/@Amazonian) does) work too
* Other decklist services are in plans
* Scraping Goldfish for meta-decks
* Scraping a singular Untapped meta-deck decklist page
* Exporting decks into a [Forge MTG](https://github.com/Card-Forge/forge) .dck format or Arena 
  decklist saved into a .txt file - with autogenerated, descriptive names based on scraped deck's 
  metadata
* Importing back into a Deck from those formats




