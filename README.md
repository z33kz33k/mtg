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
    * Individual decklist URLs/HTML tags/JSON data are extracted from container pages and further processed for decks. 
      These include:
        * Aetherhub users, events and articles
        * Archidekt folders and users
        * Cardsrealm profiles, folders, tournaments and articles
        * [CardKingdom](https://blog.cardkingdom.com) articles and authors 
        * [Cardmarket](https://www.cardmarket.com/) articles 
        * ChannelFireball players, articles and authors
        * [Commander's Herald](https://commandersherald.com) articles and authors
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
    * 88 container pages in total with 27 more in plans
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
* I compiled a list of **almost 2.3k** YT channels that feature decks in their descriptions and successfully 
  scraped them (at least 25 videos deep) so this data only waits to be creatively used now!

### How it looks in a Google Sheet
![Most popular channels](assets/channels.jpg)

### Scraped decks breakdown
| No | Format | Count | Percentage |
|:---|:-----|------:|-----------:|
| 1  | commander       | 61996 |    38.78 % |
| 2  | standard        | 35176 |    22.00 % |
| 3  | modern          | 17018 |    10.64 % |
| 4  | pauper          |  9682 |     6.06 % |
| 5  | pioneer         |  9178 |     5.74 % |
| 6  | legacy          |  4642 |     2.90 % |
| 7  | brawl           |  3725 |     2.33 % |
| 8  | historic        |  2732 |     1.71 % |
| 9  | explorer        |  2438 |     1.52 % |
| 10 | undefined       |  2387 |     1.49 % |
| 11 | paupercommander |  2049 |     1.28 % |
| 12 | duel            |  2025 |     1.27 % |
| 13 | timeless        |  1791 |     1.12 % |
| 14 | premodern       |  1067 |     0.67 % |
| 15 | irregular       |  1058 |     0.66 % |
| 16 | vintage         |   916 |     0.57 % |
| 17 | alchemy         |   856 |     0.54 % |
| 18 | oathbreaker     |   353 |     0.22 % |
| 19 | penny           |   300 |     0.19 % |
| 20 | standardbrawl   |   281 |     0.18 % |
| 21 | gladiator       |   105 |     0.07 % |
| 22 | oldschool       |    56 |     0.04 % |
| 23 | future          |    36 |     0.02 % |
| 24 | predh           |     7 |     0.00 % |
|  | TOTAL           | 159874 | 100.00 %|

| No | Source | Count | Percentage |
|:---|:-----|------:|-----------:|
| 1  | moxfield.com           | 73244 |    45.81 % |
| 2  | mtgo.com               | 15297 |     9.57 % |
| 3  | arena.decklist         | 14549 |     9.10 % |
| 4  | aetherhub.com          | 10553 |     6.60 % |
| 5  | mtggoldfish.com        | 10434 |     6.53 % |
| 6  | archidekt.com          |  5734 |     3.59 % |
| 7  | mtgdecks.net           |  4437 |     2.78 % |
| 8  | melee.gg               |  3423 |     2.14 % |
| 9  | mtg.cardsrealm.com     |  3088 |     1.93 % |
| 10 | mtga.untapped.gg       |  3055 |     1.91 % |
| 11 | tcgplayer.com          |  2756 |     1.72 % |
| 12 | tappedout.net          |  1694 |     1.06 % |
| 13 | streamdecker.com       |  1615 |     1.01 % |
| 14 | mtgtop8.com            |  1514 |     0.95 % |
| 15 | magic.gg               |  1493 |     0.93 % |
| 16 | mtgcircle.com          |  1160 |     0.73 % |
| 17 | mtgazone.com           |   715 |     0.45 % |
| 18 | deckstats.net          |   585 |     0.37 % |
| 19 | hareruyamtg.com        |   485 |     0.30 % |
| 20 | starcitygames.com      |   485 |     0.30 % |
| 21 | flexslot.gg            |   419 |     0.26 % |
| 22 | magic.wizards.com      |   378 |     0.24 % |
| 23 | scryfall.com           |   289 |     0.18 % |
| 24 | pennydreadfulmagic.com |   281 |     0.18 % |
| 25 | pauperwave.com         |   269 |     0.17 % |
| 26 | cardmarket.com         |   264 |     0.17 % |
| 27 | magic-ville.com        |   204 |     0.13 % |
| 28 | topdecked.com          |   187 |     0.12 % |
| 29 | channelfireball.com    |   171 |     0.11 % |
| 30 | manabox.app            |   169 |     0.11 % |
| 31 | edhrec.com             |   160 |     0.10 % |
| 32 | paupermtg.com          |   117 |     0.07 % |
| 33 | coolstuffinc.com       |   108 |     0.07 % |
| 34 | manatraders.com        |    87 |     0.05 % |
| 35 | mtgsearch.it           |    72 |     0.05 % |
| 36 | tcdecks.net            |    55 |     0.03 % |
| 37 | mtgstocks.com          |    53 |     0.03 % |
| 38 | manastack.com          |    40 |     0.03 % |
| 39 | mtgmeta.io             |    38 |     0.02 % |
| 40 | cyclesgaming.com       |    34 |     0.02 % |
| 41 | commandersherald.com   |    32 |     0.02 % |
| 42 | deckbox.org            |    32 |     0.02 % |
| 43 | cardhoarder.com        |    25 |     0.02 % |
| 44 | mtgvault.com           |    25 |     0.02 % |
| 45 | app.cardboard.live     |    19 |     0.01 % |
| 46 | 17lands.com            |    11 |     0.01 % |
| 47 | draftsim.com           |    10 |     0.01 % |
| 48 | magicblogs.de          |     4 |     0.00 % |
| 49 | mtgarena.pro           |     3 |     0.00 % |
| 50 | mtgotraders.com        |     1 |     0.00 % |
| 51 | playingmtg.com         |     1 |     0.00 % |
|  | TOTAL                  | 159874 | 100.00 %|
