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
    * Links to decklist services are scraped into Deck objects. 29 services are supported so far:
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
        * [Manatraders](https://www.manatraders.com)
        * [ManaStack](https://manastack.com/home)
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
        * Hareruya events
        * Goldfish tournaments and users
        * Moxfield bookmarks and users
        * MTGTop8 events
        * Streamdecker users
        * TappedOut users, folders, and user folders
        * TCDecks events
        * TCGPlayer (old-site) users
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
* I compiled a list of **over 1.3k** YT channels that feature decks in their descriptions and successfully 
  scraped them (at least 25 videos deep) so this data only waits to be creatively used now!

### How it looks in a Google Sheet
![Most popular channels](assets/channels.jpg)

### Scraped decks breakdown
| No | Format | Count | Percentage |
|:---|:-----|------:|-----------:|
| 1  | commander       | 10593 |    29.76 % |
| 2  | standard        |  9071 |    25.49 % |
| 3  | modern          |  2988 |     8.40 % |
| 4  | pioneer         |  2629 |     7.39 % |
| 5  | legacy          |  1483 |     4.17 % |
| 6  | historic        |  1183 |     3.32 % |
| 7  | brawl           |  1100 |     3.09 % |
| 8  | pauper          |  1087 |     3.05 % |
| 9  | explorer        |   974 |     2.74 % |
| 10 | timeless        |   919 |     2.58 % |
| 11 | duel            |   907 |     2.55 % |
| 12 | undefined       |   847 |     2.38 % |
| 13 | premodern       |   388 |     1.09 % |
| 14 | paupercommander |   317 |     0.89 % |
| 15 | alchemy         |   283 |     0.80 % |
| 16 | vintage         |   248 |     0.70 % |
| 17 | irregular       |   229 |     0.64 % |
| 18 | standardbrawl   |   125 |     0.35 % |
| 19 | penny           |   104 |     0.29 % |
| 20 | oathbreaker     |    50 |     0.14 % |
| 21 | gladiator       |    36 |     0.10 % |
| 22 | oldschool       |    16 |     0.04 % |
| 23 | future          |    13 |     0.04 % |
|  | TOTAL           | 35590 | 100.00 %|

| No | Source | Count | Percentage |
|:---|:-----|------:|-----------:|
| 1  | moxfield.com           | 13721 |    38.55 % |
| 2  | aetherhub.com          |  4932 |    13.86 % |
| 3  | arena.decklist         |  4750 |    13.35 % |
| 4  | mtggoldfish.com        |  4366 |    12.27 % |
| 5  | archidekt.com          |  1618 |     4.55 % |
| 6  | mtgtop8.com            |   881 |     2.48 % |
| 7  | mtga.untapped.gg       |   850 |     2.39 % |
| 8  | streamdecker.com       |   838 |     2.35 % |
| 9  | tappedout.net          |   776 |     2.18 % |
| 10 | tcgplayer.com          |   574 |     1.61 % |
| 11 | deckstats.net          |   480 |     1.35 % |
| 12 | melee.gg               |   303 |     0.85 % |
| 13 | mtgdecks.net           |   259 |     0.73 % |
| 14 | hareruyamtg.com        |   181 |     0.51 % |
| 15 | scryfall.com           |   177 |     0.50 % |
| 16 | mtgazone.com           |   171 |     0.48 % |
| 17 | magic-ville.com        |   161 |     0.45 % |
| 18 | flexslot.gg            |   127 |     0.36 % |
| 19 | topdecked.com          |    86 |     0.24 % |
| 20 | pennydreadfulmagic.com |    75 |     0.21 % |
| 21 | tcdecks.net            |    54 |     0.15 % |
| 22 | manatraders.com        |    51 |     0.14 % |
| 23 | mtg.cardsrealm.com     |    41 |     0.12 % |
| 24 | manastack.com          |    38 |     0.11 % |
| 25 | deckbox.org            |    25 |     0.07 % |
| 26 | mtgarena.pro           |    23 |     0.06 % |
| 27 | cardhoarder.com        |    20 |     0.06 % |
| 28 | app.cardboard.live     |     9 |     0.03 % |
| 29 | old.starcitygames.com  |     2 |     0.01 % |
| 30 | mtgotraders.com        |     1 |     0.00 % |
|  | TOTAL                  | 35590 | 100.00 %|
