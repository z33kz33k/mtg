# mtgcards
Scrape data on MtG decks.

### Description

This is a hobby project.

It started as a card data scraping from `MTG Goldfish`. Then, some JumpIn! packets info scraping 
was added. Then, there was some play with Limited data from [17lands](https://www.17lands.com) when 
I thought I had to bear with utter boringness of that format (before the dawn of Golden Packs on 
Arena) [_This part has been deprecated and moved to `archive` package_]. Then, I discovered I 
don't need to scrape anything because [Scryfall](https://scryfall.com).

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
* Arena, [Aetherhub](https://aetherhub.com), [Archidekt](https://archidekt.com), [Cardhoarder](https://www.cardhoarder.com), 
  [Cardsrealm](https://mtg.cardsrealm.com/en-us/), [Deckstats.net](https://deckstats.net), 
  [Flexslot](https://flexslot.gg), [Goldfish](https://www.mtggoldfish.com), [ManaStack](https://manastack.com/home), 
  [Manatraders](https://www.manatraders.com), [Moxfield](https://www.moxfield.com), 
  [MTGArena.Pro](https://mtgarena.pro), [MTGAZone](https://mtgazone.com), [MTGDecks.net](https://mtgdecks.net), 
  [MTGTop8](https://mtgtop8.com/index), [PennyDreadfulMagic](https://pennydreadfulmagic.com), [StarCityGames](https://starcitygames.com), 
  [Scryfall](https://scryfall.com), [Streamdecker](https://www.streamdecker.com/landing), [TappedOut](https://tappedout.net), 
  [TCGPlayer](https://infinite.tcgplayer.com) and [Untapped](https://mtga.untapped.gg) deck parsers 
  work, so:
    * Arena decklists pasted into video descriptions are parsed into Deck objects
    * Aetherhub, Archidekt, Cardhoarder, Cardsrealm, Deckstats.net, Flexslot, Goldfish, 
      Manatraders, ManaStack, Moxfield, MTGArena.Pro, MTGAZone, MTGDecks.net, MTGTop8, PennyDreadfulMagic 
      StarCityGames, Scryfall, Streamdecker, TappedOut, TCGPlayer and Untapped, links contained 
      in those descriptions are parsed into Deck objects
    * Both Untapped decklist types featured in YT videos are supported: regular deck and profile deck
    * Both old and new TCGPlayer sites are supported
    * Due to their dynamic nature, Untapped, TCGPlayer (new site), ManaStack, Flexslot, MTGTop8 and 
      MTGDecks.net (the last two are not much of a dynamic sites, but you do need to click a 
      consent button) are scraped using [Selenium](https://github.com/SeleniumHQ/Selenium)
    * All those mentioned above work even if they are behind shortener links and need unshortening first
    * Arena decklists in links to pastebin-like services (like 
      [Amazonian](https://www.youtube.com/@Amazonian) does) work too
* Other decklist services are in plans (but, it does seem like I've pretty much exhausted the possibilities already :))
* Scraping Goldfish and MGTAZone for meta-decks (others in plans)
* Scraping a singular Untapped meta-deck decklist page
* Exporting decks into a [Forge MTG](https://github.com/Card-Forge/forge) .dck format or Arena 
  decklist saved into a .txt file - with autogenerated, descriptive names based on scraped deck's 
  metadata
* Importing back into a Deck from those formats
* Export/import to other formats in plans
* Dumping decks, YT videos and channels to .json
* I compiled a list of almost 500 YT channels that feature decks in their descriptions and successfully scraped them, 
  so this data only waits to be creatively used now!

### How it looks in a Google Sheet
![Most popular channels](assets/channels.jpg)

### Scraped decks breakdown
![Sources & formats](assets/decks.jpg)
