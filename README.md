# mtg
Scrape data on MtG decks.

### Description

This is a hobby project.

It started as a card data scraping from `MTG Goldfish`. Then, some JumpIn! packets info scraping 
was added. Then, there was some play with Limited data from [17lands](https://www.17lands.com) when 
I thought I had to bear with utter boringness of that format (before the dawn of Golden Packs on 
Arena) [_This part has been deprecated and moved to [archive](https://github.com/z33kz33k/mtg/tree/2d5eb0c758953d38ac51840ed3e49c2c25b4fe91/mtgcards/archive) package_]. Then, I discovered I 
don't need to scrape anything because [Scryfall](https://scryfall.com).

Then, I quit (Arena).

Now, the main focus is `decks` package and `yt` module (parsing data on youtubers' decks from YT videos 
descriptions).

### What works

* Scryfall data management via downloading bulk data with 
  [scrython](https://github.com/NandaScott/Scrython) and wrapping it in convenient abstractions
* Scraping YT channels for videos with decklists in descriptions (or comments) - using no less than 
  four Python libraries to avoid bothering with Google APIs: 
    * [scrapetube](https://github.com/dermasmid/scrapetube),
    * [pytubefix](https://github.com/JuanBindez/pytubefix),
    * [youtubesearchpython](https://github.com/alexmercerind/youtube-search-python), 
    * [youtube-comment-downloader](https://github.com/egbertbouman/youtube-comment-downloader) 
* Scraping YT videos' descriptions (or comments) for decks:    
    * Text decklists in Arena/MTGO format pasted into video descriptions are parsed into Deck objects
    * Links to decklist services are scraped into Deck objects. 30 services are supported so far:
        * [Aetherhub](https://aetherhub.com)
        * [Archidekt](https://archidekt.com)
        * [CardBoard Live](https://cardboard.live)
        * [Cardhoarder](https://www.cardhoarder.com)
        * [Cardsrealm](https://mtg.cardsrealm.com/en-us/)
        * [Deckbox](https://deckbox.org)
        * [Deckstats](https://deckstats.net)
        * [Flexslot](https://flexslot.gg)
        * [Goldfish](https://www.mtggoldfish.com)
        * [Hareruya](https://www.hareruyamtg.com/en/)
        * [MagicVille](https://magic-ville.com/fr/index.php)
        * [ManaBox](https://manabox.app)
        * [ManaStack](https://manastack.com/home)
        * [Manatraders](https://www.manatraders.com)
        * [Melee.gg](https://melee.gg)
        * [Moxfield](https://www.moxfield.com)
        * [MTGArena.Pro](https://mtgarena.pro)
        * [MTGAZone](https://mtgazone.com)
        * [MTGDecks.net](https://mtgdecks.net)
        * [MTGOTraders](https://www.mtgotraders.com/store/index.html)
        * [MTGTop8](https://mtgtop8.com/index)
        * [PennyDreadfulMagic](https://pennydreadfulmagic.com)
        * [Scryfall](https://scryfall.com)
        * [StarCityGames](https://starcitygames.com)
        * [Streamdecker](https://www.streamdecker.com/landing)
        * [TappedOut](https://tappedout.net)
        * [TCDecks](https://www.tcdecks.net/index.php)
        * [TCGPlayer](https://infinite.tcgplayer.com)
        * [TopDecked](https://www.topdecked.com)
        * [Untapped](https://mtga.untapped.gg) 
    * Other decklist services are in plans (but, it does seem like I've pretty much exhausted the 
      possibilities already :))
    * Both Untapped decklist types featured in YT videos are supported: regular deck and profile deck
    * Both old and new TCGPlayer sites are supported
    * Both international and native Hareruya sites are supported 
    * Sites that need it are scraped using [Selenium](https://github.com/SeleniumHQ/Selenium)
    * All those mentioned above work even if they are behind shortener links and need unshortening first
    * Text decklists in links to pastebin-like services (like [Amazonian](https://www.youtube.com/@Amazonian) does) work too
    * If nothing is found in the video's description, then the author's comments are parsed
    * Deck's name and format are derived (from a video's title, description and keywords) if not readily available
    * Foreign cards and other that cannot be found in the downloaded Scryfall bulk data are looked 
      up with queries to the Scryfall API
    * Individual decklist URLs are extracted from container pages and further processed for decks. 
      These include:
        * Aetherhub users
        * Archidekt folders and users
        * Deckstats users
        * Hareruya events and players
        * Goldfish tournaments and users
        * Melee.gg tournaments
        * Moxfield bookmarks and users
        * MTGDecks.net tournaments
        * MTGTop8 events
        * Streamdecker users
        * TappedOut users, folders, and user folders
        * TCDecks events
        * TCGPlayer (old-site) users
        * TCGPlayer (new-site) users (both profile and search pages) and events
        * Untapped users
        * others in plans
* Assessing the meta:
    * Scraping Goldfish and MGTAZone for meta-decks (others in plans)
    * Scraping a singular Untapped meta-deck decklist page
* Exporting decks into a [Forge MTG](https://github.com/Card-Forge/forge) .dck format or Arena 
  decklist saved into a .txt file - with autogenerated, descriptive names based on scraped deck's 
  metadata
* Importing back into a Deck from those formats
* Export/import to other formats in plans
* Dumping decks, YT videos and channels to .json
* I compiled a list of **over 1.4k** YT channels that feature decks in their descriptions and successfully 
  scraped them (at least 25 videos deep) so this data only waits to be creatively used now!

### How it looks in a Google Sheet
![Most popular channels](assets/channels.jpg)

### Scraped decks breakdown
| No | Format | Count | Percentage |
|:---|:-----|------:|-----------:|
| 1  | commander       | 12491 |    31.18 % |
| 2  | standard        | 10258 |    25.61 % |
| 3  | modern          |  3188 |     7.96 % |
| 4  | pioneer         |  2850 |     7.12 % |
| 5  | legacy          |  1615 |     4.03 % |
| 6  | historic        |  1261 |     3.15 % |
| 7  | pauper          |  1231 |     3.07 % |
| 8  | brawl           |  1154 |     2.88 % |
| 9  | explorer        |  1039 |     2.59 % |
| 10 | timeless        |   993 |     2.48 % |
| 11 | duel            |   955 |     2.38 % |
| 12 | undefined       |   950 |     2.37 % |
| 13 | premodern       |   429 |     1.07 % |
| 14 | paupercommander |   361 |     0.90 % |
| 15 | vintage         |   311 |     0.78 % |
| 16 | irregular       |   307 |     0.77 % |
| 17 | alchemy         |   296 |     0.74 % |
| 18 | standardbrawl   |   134 |     0.33 % |
| 19 | penny           |   104 |     0.26 % |
| 20 | oathbreaker     |    64 |     0.16 % |
| 21 | gladiator       |    36 |     0.09 % |
| 22 | oldschool       |    16 |     0.04 % |
| 23 | future          |    13 |     0.03 % |
|  | TOTAL           | 40056 | 100.00 %|

| No | Source | Count | Percentage |
|:---|:-----|------:|-----------:|
| 1  | moxfield.com           | 15824 |    39.50 % |
| 2  | arena.decklist         |  5228 |    13.05 % |
| 3  | aetherhub.com          |  5191 |    12.96 % |
| 4  | mtggoldfish.com        |  4688 |    11.70 % |
| 5  | archidekt.com          |  1798 |     4.49 % |
| 6  | mtga.untapped.gg       |   976 |     2.44 % |
| 7  | mtgtop8.com            |   896 |     2.24 % |
| 8  | streamdecker.com       |   873 |     2.18 % |
| 9  | melee.gg               |   833 |     2.08 % |
| 10 | tappedout.net          |   791 |     1.97 % |
| 11 | tcgplayer.com          |   770 |     1.92 % |
| 12 | deckstats.net          |   495 |     1.24 % |
| 13 | mtgdecks.net           |   298 |     0.74 % |
| 14 | hareruyamtg.com        |   204 |     0.51 % |
| 15 | scryfall.com           |   183 |     0.46 % |
| 16 | mtgazone.com           |   178 |     0.44 % |
| 17 | magic-ville.com        |   163 |     0.41 % |
| 18 | flexslot.gg            |   135 |     0.34 % |
| 19 | topdecked.com          |    97 |     0.24 % |
| 20 | manabox.app            |    94 |     0.23 % |
| 21 | pennydreadfulmagic.com |    75 |     0.19 % |
| 22 | tcdecks.net            |    54 |     0.13 % |
| 23 | manatraders.com        |    51 |     0.13 % |
| 24 | mtg.cardsrealm.com     |    41 |     0.10 % |
| 25 | manastack.com          |    38 |     0.09 % |
| 26 | deckbox.org            |    27 |     0.07 % |
| 27 | mtgarena.pro           |    23 |     0.06 % |
| 28 | cardhoarder.com        |    20 |     0.05 % |
| 29 | app.cardboard.live     |     9 |     0.02 % |
| 30 | old.starcitygames.com  |     2 |     0.00 % |
| 31 | mtgotraders.com        |     1 |     0.00 % |
|  | TOTAL                  | 40056 | 100.00 %|
