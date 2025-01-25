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
    * Links to decklist services are scraped into Deck objects. 37 services are supported so far:
        * [17Lands](https://www.17lands.com)
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
        * [MTGSearch.it](https://mtgsearch.it)
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
        * TCGPlayer Infinite players (profile page), authors (search page), events and articles
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
| 1  | commander       | 33913 |    39.19 % |
| 2  | standard        | 18721 |    21.63 % |
| 3  | modern          |  6782 |     7.84 % |
| 4  | pauper          |  5392 |     6.23 % |
| 5  | pioneer         |  4914 |     5.68 % |
| 6  | legacy          |  3150 |     3.64 % |
| 7  | brawl           |  1884 |     2.18 % |
| 8  | historic        |  1791 |     2.07 % |
| 9  | explorer        |  1626 |     1.88 % |
| 10 | undefined       |  1381 |     1.60 % |
| 11 | duel            |  1346 |     1.56 % |
| 12 | timeless        |  1325 |     1.53 % |
| 13 | paupercommander |  1192 |     1.38 % |
| 14 | premodern       |   718 |     0.83 % |
| 15 | vintage         |   637 |     0.74 % |
| 16 | irregular       |   620 |     0.72 % |
| 17 | alchemy         |   434 |     0.50 % |
| 18 | penny           |   267 |     0.31 % |
| 19 | standardbrawl   |   200 |     0.23 % |
| 20 | oathbreaker     |   113 |     0.13 % |
| 21 | gladiator       |    77 |     0.09 % |
| 22 | oldschool       |    33 |     0.04 % |
| 23 | future          |    18 |     0.02 % |
|  | TOTAL           | 86534 | 100.00 %|

| No | Source | Count | Percentage |
|:---|:-----|------:|-----------:|
| 1  | moxfield.com           | 40787 |    47.13 % |
| 2  | arena.decklist         |  8384 |     9.69 % |
| 3  | aetherhub.com          |  7292 |     8.43 % |
| 4  | mtggoldfish.com        |  6937 |     8.02 % |
| 5  | mtgo.com               |  5091 |     5.88 % |
| 6  | archidekt.com          |  3585 |     4.14 % |
| 7  | mtga.untapped.gg       |  1701 |     1.97 % |
| 8  | mtgdecks.net           |  1615 |     1.87 % |
| 9  | melee.gg               |  1572 |     1.82 % |
| 10 | tappedout.net          |  1525 |     1.76 % |
| 11 | streamdecker.com       |  1062 |     1.23 % |
| 12 | mtgtop8.com            |  1053 |     1.22 % |
| 13 | magic.gg               |  1010 |     1.17 % |
| 14 | tcgplayer.com          |  1006 |     1.16 % |
| 15 | mtg.cardsrealm.com     |   981 |     1.13 % |
| 16 | deckstats.net          |   508 |     0.59 % |
| 17 | mtgazone.com           |   424 |     0.49 % |
| 18 | hareruyamtg.com        |   324 |     0.37 % |
| 19 | pennydreadfulmagic.com |   249 |     0.29 % |
| 20 | flexslot.gg            |   246 |     0.28 % |
| 21 | magic-ville.com        |   213 |     0.25 % |
| 22 | scryfall.com           |   209 |     0.24 % |
| 23 | topdecked.com          |   146 |     0.17 % |
| 24 | old.starcitygames.com  |   142 |     0.16 % |
| 25 | manabox.app            |   116 |     0.13 % |
| 26 | manatraders.com        |    56 |     0.06 % |
| 27 | tcdecks.net            |    55 |     0.06 % |
| 28 | mtgstocks.com          |    42 |     0.05 % |
| 29 | manastack.com          |    39 |     0.05 % |
| 30 | mtgsearch.it           |    37 |     0.04 % |
| 31 | deckbox.org            |    28 |     0.03 % |
| 32 | paupermtg.com          |    26 |     0.03 % |
| 33 | cardhoarder.com        |    23 |     0.03 % |
| 34 | mtgarena.pro           |    22 |     0.03 % |
| 35 | app.cardboard.live     |    16 |     0.02 % |
| 36 | 17lands.com            |    11 |     0.01 % |
| 37 | mtgotraders.com        |     1 |     0.00 % |
|  | TOTAL                  | 86534 | 100.00 %|
