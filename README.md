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
    * Links to decklist services are scraped into Deck objects. 35 services are supported so far:
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
        * [MTGStocks](https://www.mtgstocks.com)
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
    * All those mentioned above work even if they are behind shortener links and need unshortening first
    * Sites that need it are scraped using [Selenium](https://github.com/SeleniumHQ/Selenium)
    * Link trees posted in descriptions are expanded
    * Links to pastebin-like services (like [Amazonian](https://www.youtube.com/@Amazonian) does)
      , Patreon posts and Google Docs documents are expanded too and further parsed for decks
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
        * [EDHTop16](https://edhtop16.com) tournaments and commanders
        * Flexslot users
        * Goldfish tournaments, players and articles
        * Hareruya events and players
        * LigaMagic events _(with caveats)_
        * MagicVille events and users
        * ManaStack users
        * Manatraders users
        * Magic.gg events
        * Melee.gg tournaments
        * Moxfield bookmarks, users and search results
        * MTGAZone articles and authors
        * MTGDecks.net tournaments
        * MTGO events
        * MTGStocks articles
        * MTGTop8 events
        * PennyDreadfulMagic competitions and users
        * StarCityGames events, players, articles and author's decks databases
        * Streamdecker users
        * TappedOut users, folders, and user folders
        * TCDecks events
        * TCGPlayer (old-site) players
        * TCGPlayer Infinite players (profile page), authors (search page) and events
        * [TopDeck.gg](https://topdeck.gg) brackets and profiles
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
| 1  | commander       | 32727 |    39.35 % |
| 2  | standard        | 17827 |    21.43 % |
| 3  | modern          |  6360 |     7.65 % |
| 4  | pauper          |  5246 |     6.31 % |
| 5  | pioneer         |  4622 |     5.56 % |
| 6  | legacy          |  3084 |     3.71 % |
| 7  | brawl           |  1780 |     2.14 % |
| 8  | historic        |  1745 |     2.10 % |
| 9  | explorer        |  1572 |     1.89 % |
| 10 | duel            |  1335 |     1.61 % |
| 11 | undefined       |  1332 |     1.60 % |
| 12 | timeless        |  1314 |     1.58 % |
| 13 | paupercommander |  1180 |     1.42 % |
| 14 | premodern       |   696 |     0.84 % |
| 15 | vintage         |   618 |     0.74 % |
| 16 | irregular       |   610 |     0.73 % |
| 17 | alchemy         |   425 |     0.51 % |
| 18 | penny           |   267 |     0.32 % |
| 19 | standardbrawl   |   198 |     0.24 % |
| 20 | oathbreaker     |   108 |     0.13 % |
| 21 | gladiator       |    77 |     0.09 % |
| 22 | oldschool       |    33 |     0.04 % |
| 23 | future          |    17 |     0.02 % |
|  | TOTAL           | 83173 | 100.00 %|

| No | Source | Count | Percentage |
|:---|:-----|------:|-----------:|
| 1  | moxfield.com           | 39488 |    47.48 % |
| 2  | arena.decklist         |  8028 |     9.65 % |
| 3  | aetherhub.com          |  7073 |     8.50 % |
| 4  | mtggoldfish.com        |  6865 |     8.25 % |
| 5  | mtgo.com               |  4371 |     5.26 % |
| 6  | archidekt.com          |  3342 |     4.02 % |
| 7  | mtga.untapped.gg       |  1634 |     1.96 % |
| 8  | melee.gg               |  1544 |     1.86 % |
| 9  | tappedout.net          |  1515 |     1.82 % |
| 10 | mtgdecks.net           |  1508 |     1.81 % |
| 11 | mtgtop8.com            |  1051 |     1.26 % |
| 12 | streamdecker.com       |  1046 |     1.26 % |
| 13 | magic.gg               |  1010 |     1.21 % |
| 14 | tcgplayer.com          |   988 |     1.19 % |
| 15 | mtg.cardsrealm.com     |   872 |     1.05 % |
| 16 | deckstats.net          |   504 |     0.61 % |
| 17 | mtgazone.com           |   407 |     0.49 % |
| 18 | hareruyamtg.com        |   318 |     0.38 % |
| 19 | pennydreadfulmagic.com |   249 |     0.30 % |
| 20 | flexslot.gg            |   243 |     0.29 % |
| 21 | magic-ville.com        |   211 |     0.25 % |
| 22 | scryfall.com           |   207 |     0.25 % |
| 23 | old.starcitygames.com  |   142 |     0.17 % |
| 24 | topdecked.com          |   140 |     0.17 % |
| 25 | manabox.app            |   114 |     0.14 % |
| 26 | manatraders.com        |    55 |     0.07 % |
| 27 | tcdecks.net            |    54 |     0.06 % |
| 28 | mtgstocks.com          |    41 |     0.05 % |
| 29 | manastack.com          |    39 |     0.05 % |
| 30 | deckbox.org            |    28 |     0.03 % |
| 31 | paupermtg.com          |    24 |     0.03 % |
| 32 | cardhoarder.com        |    23 |     0.03 % |
| 33 | mtgarena.pro           |    22 |     0.03 % |
| 34 | app.cardboard.live     |    16 |     0.02 % |
| 35 | mtgotraders.com        |     1 |     0.00 % |
|  | TOTAL                  | 83173 | 100.00 %|
