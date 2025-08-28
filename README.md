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
        * Moxfield bookmarks, users and deck searches
        * MTGAZone articles and authors
        * MTGCircle articles
        * MTGDecks.net tournaments and articles
        * MTGMeta.io tournaments and articles _(defunct, scraped via Wayback Machine)_
        * [MTGO](https://www.mtgo.com/en/mtgo) events
        * [MTGRocks](https://mtgrocks.com) articles and authors
        * MTGStocks articles
        * MTGTop8 events
        * MTGVault users
        * [Pauperwave](https://www.pauperwave.com) articles
        * PennyDreadfulMagic competitions and users
        * PlayingMTG tournaments and articles
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
* Dumping data to JSON
* Semi-automatic discovery of new channels
* I compiled a list of **over 2.5k** YT channels that feature decks in their descriptions and successfully 
  scraped them (at least 25 videos deep) so this data only waits to be creatively used now!

### How it looks in a Google Sheet
![Most popular channels](assets/channels.jpg)

### Scraped decks breakdown
**29th Aug 2025**
| No | Format | Count | Percentage |
|:---|:-----|------:|-----------:|
| 1  | commander       | 79227 |    37.96 % |
| 2  | standard        | 49252 |    23.60 % |
| 3  | modern          | 21818 |    10.45 % |
| 4  | pauper          | 13052 |     6.25 % |
| 5  | pioneer         | 11916 |     5.71 % |
| 6  | brawl           |  5966 |     2.86 % |
| 7  | legacy          |  5532 |     2.65 % |
| 8  | historic        |  3421 |     1.64 % |
| 9  | undefined       |  3088 |     1.48 % |
| 10 | explorer        |  2519 |     1.21 % |
| 11 | duel            |  2245 |     1.08 % |
| 12 | paupercommander |  2125 |     1.02 % |
| 13 | timeless        |  2088 |     1.00 % |
| 14 | premodern       |  1407 |     0.67 % |
| 15 | irregular       |  1388 |     0.67 % |
| 16 | alchemy         |  1265 |     0.61 % |
| 17 | vintage         |  1085 |     0.52 % |
| 18 | oathbreaker     |   394 |     0.19 % |
| 19 | penny           |   337 |     0.16 % |
| 20 | standardbrawl   |   314 |     0.15 % |
| 21 | gladiator       |   129 |     0.06 % |
| 22 | oldschool       |    76 |     0.04 % |
| 23 | future          |    54 |     0.03 % |
| 24 | predh           |    12 |     0.01 % |
|  | TOTAL           | 208710 | 100.00 %|

| No | Source | Count | Percentage |
|:---|:-----|------:|-----------:|
| 1  | moxfield.com           | 86865 |    41.62 % |
| 2  | mtgo.com               | 24191 |    11.59 % |
| 3  | arena.decklist         | 18560 |     8.89 % |
| 4  | aetherhub.com          | 12831 |     6.15 % |
| 5  | mtggoldfish.com        | 12173 |     5.83 % |
| 6  | archidekt.com          |  7476 |     3.58 % |
| 7  | mtgdecks.net           |  7295 |     3.50 % |
| 8  | topdeck.gg             |  5592 |     2.68 % |
| 9  | mtg.cardsrealm.com     |  4254 |     2.04 % |
| 10 | mtga.untapped.gg       |  4006 |     1.92 % |
| 11 | mtgcircle.com          |  3840 |     1.84 % |
| 12 | melee.gg               |  3630 |     1.74 % |
| 13 | tcgplayer.com          |  3573 |     1.71 % |
| 14 | tappedout.net          |  2005 |     0.96 % |
| 15 | streamdecker.com       |  1845 |     0.88 % |
| 16 | magic.gg               |  1733 |     0.83 % |
| 17 | mtgtop8.com            |  1671 |     0.80 % |
| 18 | hareruyamtg.com        |   916 |     0.44 % |
| 19 | magic.wizards.com      |   767 |     0.37 % |
| 20 | mtgazone.com           |   745 |     0.36 % |
| 21 | deckstats.net          |   618 |     0.30 % |
| 22 | flexslot.gg            |   550 |     0.26 % |
| 23 | starcitygames.com      |   516 |     0.25 % |
| 24 | pauperwave.com         |   333 |     0.16 % |
| 25 | pennydreadfulmagic.com |   318 |     0.15 % |
| 26 | scryfall.com           |   281 |     0.13 % |
| 27 | cardmarket.com         |   277 |     0.13 % |
| 28 | magic-ville.com        |   225 |     0.11 % |
| 29 | topdecked.com          |   207 |     0.10 % |
| 30 | edhrec.com             |   187 |     0.09 % |
| 31 | manabox.app            |   175 |     0.08 % |
| 32 | channelfireball.com    |   171 |     0.08 % |
| 33 | coolstuffinc.com       |   134 |     0.06 % |
| 34 | paupermtg.com          |   123 |     0.06 % |
| 35 | manatraders.com        |    99 |     0.05 % |
| 36 | mtgsearch.it           |    97 |     0.05 % |
| 37 | tcdecks.net            |    80 |     0.04 % |
| 38 | mtgstocks.com          |    50 |     0.02 % |
| 39 | commandersherald.com   |    43 |     0.02 % |
| 40 | cyclesgaming.com       |    41 |     0.02 % |
| 41 | manastack.com          |    40 |     0.02 % |
| 42 | mtgmeta.io             |    38 |     0.02 % |
| 43 | deckbox.org            |    34 |     0.02 % |
| 44 | cardhoarder.com        |    25 |     0.01 % |
| 45 | mtgvault.com           |    25 |     0.01 % |
| 46 | app.cardboard.live     |    19 |     0.01 % |
| 47 | draftsim.com           |    16 |     0.01 % |
| 48 | 17lands.com            |    11 |     0.01 % |
| 49 | magicblogs.de          |     4 |     0.00 % |
| 50 | mtgarena.pro           |     3 |     0.00 % |
| 51 | mtgotraders.com        |     1 |     0.00 % |
| 52 | playingmtg.com         |     1 |     0.00 % |
|  | TOTAL                  | 208710 | 100.00 %|
