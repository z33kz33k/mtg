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

Now, the main focus is `deck` and `yt` packages (parsing data on youtubers' decks from 
YT videos descriptions).

### What works

* Scryfall data management via downloading bulk data with 
  [scrython](https://github.com/NandaScott/Scrython) and wrapping it in convenient abstractions
* Scraping YouTube channels for decklist-featuring video descriptions (or author's comments) - using 
  no less than four Python libraries to avoid bothering with Google APIs: 
    * [scrapetube](https://github.com/dermasmid/scrapetube),
    * [pytubefix](https://github.com/JuanBindez/pytubefix),
    * [youtubesearchpython](https://github.com/alexmercerind/youtube-search-python), 
    * [youtube-comment-downloader](https://github.com/egbertbouman/youtube-comment-downloader) 
* Parsing those descriptions (or author's comments) for decks:    
    * Pasted text decklists in Arena/MTGO format are parsed into Deck objects
    * Links to decklist sites are scraped into Deck objects. 44 sites are supported so far:
        * [17Lands](https://www.17lands.com)
        * [Aetherhub](https://aetherhub.com)
        * [Archidekt](https://archidekt.com)
        * [CardBoard Live](https://cardboard.live)
        * [Cardhoarder](https://www.cardhoarder.com)
        * [Cardsrealm](https://mtg.cardsrealm.com/en-us/)
        * [ChannelFireball](https://www.channelfireball.com)
        * [Deckbox](https://deckbox.org)
        * [Deckstats](https://deckstats.net)
        * [Draftsim](https://draftsim.com)
        * [EDHREC](https://edhrec.com)
        * [Flexslot](https://flexslot.gg)
        * [Goldfish](https://www.mtggoldfish.com)
        * [Hareruya](https://www.hareruyamtg.com/en/)
        * [LigaMagic](https://www.ligamagic.com.br/?view=home) _(with caveats)_
        * [MagicVille](https://magic-ville.com/fr/index.php)
        * [ManaBox](https://manabox.app)
        * [ManaStack](https://manastack.com/home)
        * [Manatraders](https://www.manatraders.com)
        * [Melee.gg](https://melee.gg)
        * [Moxfield](https://www.moxfield.com)
        * [MTGArena.Pro](https://mtgarena.pro)
        * [MTGAZone](https://mtgazone.com)
        * [MTGCircle](https://mtgcircle.com)
        * [MTGDecks.net](https://mtgdecks.net)
        * [MTGJSON](https://mtgjson.com)
        * MTGMeta.io _(defunct, scraped via Wayback Machine)_
        * [MTGSearch.it](https://mtgsearch.it)
        * [MTGStocks](https://www.mtgstocks.com)
        * [MTGOTraders](https://www.mtgotraders.com/store/index.html)
        * [MTGTop8](https://mtgtop8.com/index)
        * [MTGVault](https://www.mtgvault.com)
        * [PauperMTG](https://paupermtg.com)
        * [PennyDreadfulMagic](https://pennydreadfulmagic.com)
        * [PlayingMTG](https://playingmtg.com)
        * [Scryfall](https://scryfall.com)
        * [StarCityGames](https://starcitygames.com)
        * [Streamdecker](https://www.streamdecker.com/landing)
        * [TappedOut](https://tappedout.net)
        * [TCDecks](https://www.tcdecks.net/index.php)
        * [TCGPlayer](https://infinite.tcgplayer.com)
        * [TCGRocks](https://tcgrocks.com)
        * [TopDecked](https://www.topdecked.com)
        * [Untapped](https://mtga.untapped.gg) 
    * 3 more decklist sites in plans 
    * Both Aetherhub decklist types featured in YT videos are supported: regular deck and write-up deck
    * Both Archidekt decklist types featured in YT videos are supported: regular deck and snapshot deck
    * Both EDHREC decklist types featured in YT videos are supported: preview deck and average deck
    * Both MTGCircle decklist types featured in YT videos are supported: video deck and regular deck
    * All Untapped decklist types featured in YT videos are supported: regular, profile and meta deck
    * Both old TCGPlayer site and TCGPlayer Infinite are supported
    * Both international and native Hareruya sites are supported 
    * LigaMagic is the only sore spot that demands from me investing in scraping APIs to bypass 
      their CloudFlare protection and be fully supported (anyway, the logic to scrape them is already in place)
    * All those mentioned above work even if they are behind shortener links and need unshortening first
    * Sites that need it are scraped using [Selenium](https://github.com/SeleniumHQ/Selenium)
    * Link trees posted in descriptions/comments are expanded
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
        * [Cardmarket](https://www.cardmarket.com/) articles 
        * ChannelFireball players, articles and authors
        * [Commander's Herald](https://commandersherald.com) articles
        * [CoolStuffInc](https://www.coolstuffinc.com) articles and authors
        * [CyclesGaming](https://cyclesgaming.com) articles
        * Deckbox users and events
        * Deckstats users
        * Draftsim articles and authors
        * EDHREC authors, articles and article searches
        * [EDHTop16](https://edhtop16.com) tournaments and commanders
        * Flexslot users
        * Goldfish tournaments, players and articles
        * Hareruya events and players
        * LigaMagic events _(with caveats)_
        * MagicVille events and users
        * ManaStack users
        * Manatraders users
        * [Magic.gg](https://magic.gg) events
        * [MagicBlogs.de](https://magicblogs.de) articles
        * Melee.gg profiles and tournaments
        * Moxfield bookmarks, users and search results
        * MTGAZone articles and authors
        * MTGCircle articles
        * MTGDecks.net tournaments and articles
        * MTGMeta.io articles and tournaments _(defunct, scraped via Wayback Machine)_
        * [MTGO](https://www.mtgo.com/en/mtgo) events
        * [MTGRocks](https://mtgrocks.com) articles and authors
        * MTGStocks articles
        * MTGTop8 events
        * MTGVault users
        * [Pauperwave](https://www.pauperwave.com) articles
        * PennyDreadfulMagic competitions and users
        * PlayingMTG articles and tournaments
        * StarCityGames events, players, articles and author's decks databases
        * Streamdecker users
        * TappedOut users, folders, and user folders
        * TCDecks events
        * TCGPlayer (old-site) players
        * TCGPlayer Infinite players, authors, author searches, author deck panes, events and articles
        * [TopDeck.gg](https://topdeck.gg) brackets and profiles
        * Untapped profiles
        * [WotC (official MTG site)](https://magic.wizards.com/en) articles
    * 86 container pages in total with 20 more in plans
* Assessing the meta:
    * Goldfish
    * MGTAZone 
    * (others in plans)
* Exporting decks into [XMage](https://xmage.today) .dck format, [Forge MTG](https://github.com/Card-Forge/forge) .dck format or Arena 
  decklist saved into a .txt file - with autogenerated, descriptive names based on scraped deck's 
  metadata
* Importing back into a Deck from those formats
* Export/import to other formats in plans
* Dumping decks, YT videos and channels to .json
* Semi-automatic discovery of new channels
* I compiled a list of **almost 2.2k** YT channels that feature decks in their descriptions and successfully 
  scraped them (at least 25 videos deep) so this data only waits to be creatively used now!

### How it looks in a Google Sheet
![Most popular channels](assets/channels.jpg)

### Scraped decks breakdown
| No | Format | Count | Percentage |
|:---|:-----|------:|-----------:|
| 1  | commander       | 57211 |    39.10 % |
| 2  | standard        | 31972 |    21.85 % |
| 3  | modern          | 15371 |    10.51 % |
| 4  | pauper          |  8817 |     6.03 % |
| 5  | pioneer         |  8279 |     5.66 % |
| 6  | legacy          |  4422 |     3.02 % |
| 7  | brawl           |  3047 |     2.08 % |
| 8  | historic        |  2475 |     1.69 % |
| 9  | explorer        |  2336 |     1.60 % |
| 10 | undefined       |  2144 |     1.47 % |
| 11 | paupercommander |  2016 |     1.38 % |
| 12 | duel            |  1895 |     1.30 % |
| 13 | timeless        |  1706 |     1.17 % |
| 14 | premodern       |   960 |     0.66 % |
| 15 | irregular       |   938 |     0.64 % |
| 16 | vintage         |   873 |     0.60 % |
| 17 | alchemy         |   768 |     0.52 % |
| 18 | oathbreaker     |   346 |     0.24 % |
| 19 | penny           |   299 |     0.20 % |
| 20 | standardbrawl   |   263 |     0.18 % |
| 21 | gladiator       |    86 |     0.06 % |
| 22 | oldschool       |    50 |     0.03 % |
| 23 | future          |    32 |     0.02 % |
| 24 | predh           |     7 |     0.00 % |
|  | TOTAL           | 146313 | 100.00 %|

| No | Source | Count | Percentage |
|:---|:-----|------:|-----------:|
| 1  | moxfield.com           | 67647 |    46.23 % |
| 2  | arena.decklist         | 13262 |     9.06 % |
| 3  | mtgo.com               | 12961 |     8.86 % |
| 4  | mtggoldfish.com        |  9994 |     6.83 % |
| 5  | aetherhub.com          |  9815 |     6.71 % |
| 6  | archidekt.com          |  5460 |     3.73 % |
| 7  | mtgdecks.net           |  4388 |     3.00 % |
| 8  | melee.gg               |  2892 |     1.98 % |
| 9  | mtga.untapped.gg       |  2812 |     1.92 % |
| 10 | mtg.cardsrealm.com     |  2532 |     1.73 % |
| 11 | tcgplayer.com          |  2481 |     1.70 % |
| 12 | tappedout.net          |  1661 |     1.14 % |
| 13 | streamdecker.com       |  1546 |     1.06 % |
| 14 | magic.gg               |  1421 |     0.97 % |
| 15 | mtgtop8.com            |  1358 |     0.93 % |
| 16 | mtgazone.com           |   706 |     0.48 % |
| 17 | deckstats.net          |   570 |     0.39 % |
| 18 | mtgcircle.com          |   527 |     0.36 % |
| 19 | starcitygames.com      |   461 |     0.32 % |
| 20 | hareruyamtg.com        |   452 |     0.31 % |
| 21 | flexslot.gg            |   381 |     0.26 % |
| 22 | magic.wizards.com      |   337 |     0.23 % |
| 23 | pennydreadfulmagic.com |   280 |     0.19 % |
| 24 | pauperwave.com         |   277 |     0.19 % |
| 25 | scryfall.com           |   273 |     0.19 % |
| 26 | cardmarket.com         |   261 |     0.18 % |
| 27 | magic-ville.com        |   199 |     0.14 % |
| 28 | topdecked.com          |   180 |     0.12 % |
| 29 | channelfireball.com    |   171 |     0.12 % |
| 30 | manabox.app            |   152 |     0.10 % |
| 31 | edhrec.com             |   150 |     0.10 % |
| 32 | coolstuffinc.com       |   107 |     0.07 % |
| 33 | paupermtg.com          |    97 |     0.07 % |
| 34 | manatraders.com        |    85 |     0.06 % |
| 35 | mtgsearch.it           |    66 |     0.05 % |
| 36 | tcdecks.net            |    55 |     0.04 % |
| 37 | mtgstocks.com          |    53 |     0.04 % |
| 38 | manastack.com          |    40 |     0.03 % |
| 39 | mtgmeta.io             |    38 |     0.03 % |
| 40 | cyclesgaming.com       |    31 |     0.02 % |
| 41 | deckbox.org            |    30 |     0.02 % |
| 42 | cardhoarder.com        |    25 |     0.02 % |
| 43 | mtgvault.com           |    25 |     0.02 % |
| 44 | app.cardboard.live     |    19 |     0.01 % |
| 45 | 17lands.com            |    11 |     0.01 % |
| 46 | draftsim.com           |    10 |     0.01 % |
| 47 | commandersherald.com   |     5 |     0.00 % |
| 48 | magicblogs.de          |     4 |     0.00 % |
| 49 | mtgarena.pro           |     3 |     0.00 % |
| 50 | mtgotraders.com        |     1 |     0.00 % |
| 51 | playingmtg.com         |     1 |     0.00 % |
|  | TOTAL                  | 146313 | 100.00 %|
