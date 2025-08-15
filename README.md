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
    * Links to decklist sites are scraped into Deck objects. 45 sites are supported so far:
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
        * [TopDeck](https://topdeck.gg)
        * [TopDecked](https://www.topdecked.com)
        * [Untapped](https://mtga.untapped.gg) 
    * 4 more decklist sites in plans 
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
        * Cardsrealm profiles, folders, tournaments, articles, authors and article searches
        * [CardKingdom](https://blog.cardkingdom.com) articles and authors 
        * [Cardmarket](https://www.cardmarket.com/) articles and writers
        * ChannelFireball players, articles and authors
        * [Commander's Herald](https://commandersherald.com) articles and authors
        * [CoolStuffInc](https://www.coolstuffinc.com) articles and authors
        * [CyclesGaming](https://cyclesgaming.com) articles
        * Deckbox users and events
        * Deckstats users
        * Draftsim articles and authors
        * EDHREC authors, articles and article searches
        * [EDHTop16](https://edhtop16.com) tournaments and commanders
        * Flexslot sideboards, articles and users
        * Goldfish tournaments, players, articles and authors
        * Hareruya events, players, articles and authors
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
        * TopDeck.gg brackets and profiles
        * Untapped profiles
        * [WotC (official MTG site)](https://magic.wizards.com/en) articles
    * 96 container pages in total with 22 more in plans
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
* I compiled a list of **over 2.5k** YT channels that feature decks in their descriptions and successfully 
  scraped them (at least 25 videos deep) so this data only waits to be creatively used now!

### How it looks in a Google Sheet
![Most popular channels](assets/channels.jpg)

### Scraped decks breakdown
| No | Format | Count | Percentage |
|:---|:-----|------:|-----------:|
| 1  | commander       | 74553 |    37.36 % |
| 2  | standard        | 47517 |    23.81 % |
| 3  | modern          | 21006 |    10.53 % |
| 4  | pauper          | 12771 |     6.40 % |
| 5  | pioneer         | 11494 |     5.76 % |
| 6  | brawl           |  5569 |     2.79 % |
| 7  | legacy          |  5332 |     2.67 % |
| 8  | historic        |  3273 |     1.64 % |
| 9  | undefined       |  3033 |     1.52 % |
| 10 | explorer        |  2519 |     1.26 % |
| 11 | duel            |  2229 |     1.12 % |
| 12 | paupercommander |  2121 |     1.06 % |
| 13 | timeless        |  2035 |     1.02 % |
| 14 | irregular       |  1357 |     0.68 % |
| 15 | premodern       |  1351 |     0.68 % |
| 16 | alchemy         |  1059 |     0.53 % |
| 17 | vintage         |  1043 |     0.52 % |
| 18 | oathbreaker     |   394 |     0.20 % |
| 19 | penny           |   337 |     0.17 % |
| 20 | standardbrawl   |   312 |     0.16 % |
| 21 | gladiator       |   129 |     0.06 % |
| 22 | oldschool       |    70 |     0.04 % |
| 23 | future          |    52 |     0.03 % |
| 24 | predh           |    12 |     0.01 % |
|  | TOTAL           | 199568 | 100.00 %|

| No | Source | Count | Percentage |
|:---|:-----|------:|-----------:|
| 1  | moxfield.com           | 85409 |    42.80 % |
| 2  | mtgo.com               | 22689 |    11.37 % |
| 3  | arena.decklist         | 18026 |     9.03 % |
| 4  | aetherhub.com          | 12536 |     6.28 % |
| 5  | mtggoldfish.com        | 11955 |     5.99 % |
| 6  | archidekt.com          |  7335 |     3.68 % |
| 7  | mtgdecks.net           |  6813 |     3.41 % |
| 8  | mtg.cardsrealm.com     |  4070 |     2.04 % |
| 9  | mtga.untapped.gg       |  3843 |     1.93 % |
| 10 | melee.gg               |  3626 |     1.82 % |
| 11 | tcgplayer.com          |  3513 |     1.76 % |
| 12 | mtgcircle.com          |  3217 |     1.61 % |
| 13 | topdeck.gg             |  2273 |     1.14 % |
| 14 | tappedout.net          |  1996 |     1.00 % |
| 15 | streamdecker.com       |  1818 |     0.91 % |
| 16 | magic.gg               |  1696 |     0.85 % |
| 17 | mtgtop8.com            |  1666 |     0.83 % |
| 18 | hareruyamtg.com        |   908 |     0.45 % |
| 19 | magic.wizards.com      |   757 |     0.38 % |
| 20 | mtgazone.com           |   745 |     0.37 % |
| 21 | deckstats.net          |   613 |     0.31 % |
| 22 | flexslot.gg            |   534 |     0.27 % |
| 23 | starcitygames.com      |   508 |     0.25 % |
| 24 | pauperwave.com         |   333 |     0.17 % |
| 25 | pennydreadfulmagic.com |   318 |     0.16 % |
| 26 | scryfall.com           |   280 |     0.14 % |
| 27 | cardmarket.com         |   277 |     0.14 % |
| 28 | magic-ville.com        |   225 |     0.11 % |
| 29 | topdecked.com          |   203 |     0.10 % |
| 30 | manabox.app            |   175 |     0.09 % |
| 31 | channelfireball.com    |   171 |     0.09 % |
| 32 | edhrec.com             |   168 |     0.08 % |
| 33 | coolstuffinc.com       |   131 |     0.07 % |
| 34 | paupermtg.com          |   122 |     0.06 % |
| 35 | manatraders.com        |    97 |     0.05 % |
| 36 | mtgsearch.it           |    93 |     0.05 % |
| 37 | tcdecks.net            |    79 |     0.04 % |
| 38 | mtgstocks.com          |    50 |     0.03 % |
| 39 | commandersherald.com   |    43 |     0.02 % |
| 40 | cyclesgaming.com       |    41 |     0.02 % |
| 41 | manastack.com          |    40 |     0.02 % |
| 42 | mtgmeta.io             |    38 |     0.02 % |
| 43 | deckbox.org            |    34 |     0.02 % |
| 44 | cardhoarder.com        |    25 |     0.01 % |
| 45 | mtgvault.com           |    25 |     0.01 % |
| 46 | app.cardboard.live     |    19 |     0.01 % |
| 47 | draftsim.com           |    15 |     0.01 % |
| 48 | 17lands.com            |    11 |     0.01 % |
| 49 | magicblogs.de          |     4 |     0.00 % |
| 50 | mtgarena.pro           |     3 |     0.00 % |
| 51 | mtgotraders.com        |     1 |     0.00 % |
| 52 | playingmtg.com         |     1 |     0.00 % |
|  | TOTAL                  | 199568 | 100.00 %|
