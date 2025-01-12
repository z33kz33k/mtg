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
    * Links to decklist services are scraped into Deck objects. 34 services are supported so far:
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
        * [LigaMagic](https://www.ligamagic.com.br/?view=home) _(with caveats)_
        * [Magic.gg](https://magic.gg)
        * [MagicVille](https://magic-ville.com/fr/index.php)
        * [ManaBox](https://manabox.app)
        * [ManaStack](https://manastack.com/home)
        * [Manatraders](https://www.manatraders.com)
        * [Melee.gg](https://melee.gg)
        * [Moxfield](https://www.moxfield.com)
        * [MTGArena.Pro](https://mtgarena.pro)
        * [MTGAZone](https://mtgazone.com)
        * [MTGDecks.net](https://mtgdecks.net)
        * [MTGO](https://www.mtgo.com/en/mtgo)
        * [MTGOTraders](https://www.mtgotraders.com/store/index.html)
        * [MTGTop8](https://mtgtop8.com/index)
        * [PauperMTG](https://paupermtg.com)
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
    * Both Aetherhub decklist types featured in YT videos are supported: regular deck and write-up deck
    * Both Untapped decklist types featured in YT videos are supported: regular deck and profile deck
    * Both old TCGPlayer site and TCGPlayer Infinite are supported
    * Both international and native Hareruya sites are supported 
    * LigaMagic is the only sore spot that demands from me investing in scraping APIs to bypass 
      their CloudFlare protection and be fully supported (anyway, the logic to scrape them is already in place)
    * Sites that need it are scraped using [Selenium](https://github.com/SeleniumHQ/Selenium)
    * Link trees posted in descriptions are expanded
    * All those mentioned above work even if they are behind shortener links and need unshortening first
    * Text decklists in links to pastebin-like services (like [Amazonian](https://www.youtube.com/@Amazonian) does) work too
    * If nothing is found in the video's description, then the author's comments are parsed
    * Deck's name and format are derived (from a video's title, description and keywords) if not readily available
    * Foreign cards and other that cannot be found in the downloaded Scryfall bulk data are looked 
      up with queries to the Scryfall API
    * Individual decklists are extracted from container pages and further processed for decks. 
      These include:
        * Aetherhub users, events and articles
        * Archidekt folders and users
        * Cardsrealm profiles, folders, tournaments and articles
        * Deckbox users and events
        * Deckstats users
        * Flexslot users
        * Goldfish tournaments, players and articles
        * Hareruya events and players
        * LigaMagic events _(with caveats)_
        * MagicVille events and users
        * ManaStack users
        * Manatraders users
        * Magic.gg events
        * Melee.gg tournaments
        * Moxfield bookmarks and users
        * MTGAZone articles and authors
        * MTGDecks.net tournaments
        * MTGO events
        * MTGTop8 events
        * PennyDreadfulMagic competitions and users
        * StarCityGames events, players, articles and author's decks databases
        * Streamdecker users
        * TappedOut users, folders, and user folders
        * TCDecks events
        * TCGPlayer (old-site) players
        * TCGPlayer Infinite players (profile page), authors (search page) and events
        * Untapped profiles
* Assessing the meta:
    * Scraping Goldfish and MGTAZone for meta-decks (others in plans)
    * Scraping a singular Untapped meta-deck decklist page
* Exporting decks into a [Forge MTG](https://github.com/Card-Forge/forge) .dck format or Arena 
  decklist saved into a .txt file - with autogenerated, descriptive names based on scraped deck's 
  metadata
* Importing back into a Deck from those formats
* Export/import to other formats in plans
* Dumping decks, YT videos and channels to .json
* I compiled a list of **over 1.7k** YT channels that feature decks in their descriptions and successfully 
  scraped them (at least 25 videos deep) so this data only waits to be creatively used now!

### How it looks in a Google Sheet
![Most popular channels](assets/channels.jpg)

### Scraped decks breakdown
| No | Format | Count | Percentage |
|:---|:-----|------:|-----------:|
| 1  | commander       | 20104 |    29.81 % |
| 2  | standard        | 17037 |    25.26 % |
| 3  | modern          |  5955 |     8.83 % |
| 4  | pauper          |  5029 |     7.46 % |
| 5  | pioneer         |  4292 |     6.36 % |
| 6  | legacy          |  2846 |     4.22 % |
| 7  | brawl           |  1723 |     2.55 % |
| 8  | historic        |  1704 |     2.53 % |
| 9  | explorer        |  1512 |     2.24 % |
| 10 | undefined       |  1333 |     1.98 % |
| 11 | timeless        |  1292 |     1.92 % |
| 12 | duel            |  1265 |     1.88 % |
| 13 | premodern       |   644 |     0.95 % |
| 14 | vintage         |   586 |     0.87 % |
| 15 | irregular       |   539 |     0.80 % |
| 16 | paupercommander |   482 |     0.71 % |
| 17 | alchemy         |   417 |     0.62 % |
| 18 | penny           |   279 |     0.41 % |
| 19 | standardbrawl   |   190 |     0.28 % |
| 20 | oathbreaker     |    90 |     0.13 % |
| 21 | gladiator       |    77 |     0.11 % |
| 22 | oldschool       |    34 |     0.05 % |
| 23 | future          |    16 |     0.02 % |
|  | TOTAL           | 67446 | 100.00 %|

| No | Source | Count | Percentage |
|:---|:-----|------:|-----------:|
| 1  | moxfield.com           | 25647 |    38.03 % |
| 2  | arena.decklist         |  7780 |    11.54 % |
| 3  | aetherhub.com          |  6931 |    10.28 % |
| 4  | mtggoldfish.com        |  6512 |     9.66 % |
| 5  | mtgo.com               |  3841 |     5.69 % |
| 6  | archidekt.com          |  3168 |     4.70 % |
| 7  | mtga.untapped.gg       |  1573 |     2.33 % |
| 8  | melee.gg               |  1492 |     2.21 % |
| 9  | tappedout.net          |  1488 |     2.21 % |
| 10 | mtgdecks.net           |  1406 |     2.08 % |
| 11 | streamdecker.com       |  1097 |     1.63 % |
| 12 | mtgtop8.com            |  1049 |     1.56 % |
| 13 | magic.gg               |  1010 |     1.50 % |
| 14 | tcgplayer.com          |   952 |     1.41 % |
| 15 | mtg.cardsrealm.com     |   758 |     1.12 % |
| 16 | deckstats.net          |   512 |     0.76 % |
| 17 | mtgazone.com           |   405 |     0.60 % |
| 18 | hareruyamtg.com        |   299 |     0.44 % |
| 19 | pennydreadfulmagic.com |   250 |     0.37 % |
| 20 | flexslot.gg            |   227 |     0.34 % |
| 21 | magic-ville.com        |   210 |     0.31 % |
| 22 | scryfall.com           |   205 |     0.30 % |
| 23 | topdecked.com          |   134 |     0.20 % |
| 24 | old.starcitygames.com  |   134 |     0.20 % |
| 25 | manabox.app            |   108 |     0.16 % |
| 26 | manatraders.com        |    55 |     0.08 % |
| 27 | tcdecks.net            |    54 |     0.08 % |
| 28 | manastack.com          |    38 |     0.06 % |
| 29 | deckbox.org            |    27 |     0.04 % |
| 30 | paupermtg.com          |    24 |     0.04 % |
| 31 | mtgarena.pro           |    23 |     0.03 % |
| 32 | cardhoarder.com        |    20 |     0.03 % |
| 33 | app.cardboard.live     |    16 |     0.02 % |
| 34 | mtgotraders.com        |     1 |     0.00 % |
|  | TOTAL                  | 67446 | 100.00 %|
