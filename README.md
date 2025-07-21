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
        * TopDeck.gg brackets and profiles
        * Untapped profiles
        * [WotC (official MTG site)](https://magic.wizards.com/en) articles
    * 88 container pages in total with 28 more in plans
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
* I compiled a list of **almost 2.5k** YT channels that feature decks in their descriptions and successfully 
  scraped them (at least 25 videos deep) so this data only waits to be creatively used now!

### How it looks in a Google Sheet
![Most popular channels](assets/channels.jpg)

### Scraped decks breakdown
| No | Format | Count | Percentage |
|:---|:-----|------:|-----------:|
| 1  | commander       | 70460 |    37.89 % |
| 2  | standard        | 43454 |    23.37 % |
| 3  | modern          | 19582 |    10.53 % |
| 4  | pauper          | 11618 |     6.25 % |
| 5  | pioneer         | 10532 |     5.66 % |
| 6  | legacy          |  5062 |     2.72 % |
| 7  | brawl           |  4918 |     2.64 % |
| 8  | historic        |  3062 |     1.65 % |
| 9  | undefined       |  2856 |     1.54 % |
| 10 | explorer        |  2519 |     1.35 % |
| 11 | duel            |  2131 |     1.15 % |
| 12 | paupercommander |  2091 |     1.12 % |
| 13 | timeless        |  1919 |     1.03 % |
| 14 | irregular       |  1277 |     0.69 % |
| 15 | premodern       |  1240 |     0.67 % |
| 16 | vintage         |  1007 |     0.54 % |
| 17 | alchemy         |   996 |     0.54 % |
| 18 | oathbreaker     |   368 |     0.20 % |
| 19 | penny           |   334 |     0.18 % |
| 20 | standardbrawl   |   308 |     0.17 % |
| 21 | gladiator       |   120 |     0.06 % |
| 22 | oldschool       |    60 |     0.03 % |
| 23 | future          |    42 |     0.02 % |
| 24 | predh           |    12 |     0.01 % |
|  | TOTAL           | 185968 | 100.00 %|

| No | Source | Count | Percentage |
|:---|:-----|------:|-----------:|
| 1  | moxfield.com           | 81703 |    43.93 % |
| 2  | mtgo.com               | 19649 |    10.57 % |
| 3  | arena.decklist         | 16703 |     8.98 % |
| 4  | aetherhub.com          | 11736 |     6.31 % |
| 5  | mtggoldfish.com        | 11434 |     6.15 % |
| 6  | archidekt.com          |  7108 |     3.82 % |
| 7  | mtgdecks.net           |  6745 |     3.63 % |
| 8  | mtg.cardsrealm.com     |  3630 |     1.95 % |
| 9  | melee.gg               |  3570 |     1.92 % |
| 10 | mtga.untapped.gg       |  3532 |     1.90 % |
| 11 | tcgplayer.com          |  3444 |     1.85 % |
| 12 | mtgcircle.com          |  2382 |     1.28 % |
| 13 | tappedout.net          |  1918 |     1.03 % |
| 14 | streamdecker.com       |  1762 |     0.95 % |
| 15 | magic.gg               |  1622 |     0.87 % |
| 16 | mtgtop8.com            |  1573 |     0.85 % |
| 17 | topdeck.gg             |   957 |     0.51 % |
| 18 | mtgazone.com           |   742 |     0.40 % |
| 19 | magic.wizards.com      |   721 |     0.39 % |
| 20 | deckstats.net          |   599 |     0.32 % |
| 21 | hareruyamtg.com        |   556 |     0.30 % |
| 22 | starcitygames.com      |   490 |     0.26 % |
| 23 | flexslot.gg            |   467 |     0.25 % |
| 24 | pauperwave.com         |   325 |     0.17 % |
| 25 | pennydreadfulmagic.com |   315 |     0.17 % |
| 26 | scryfall.com           |   275 |     0.15 % |
| 27 | cardmarket.com         |   273 |     0.15 % |
| 28 | magic-ville.com        |   210 |     0.11 % |
| 29 | topdecked.com          |   201 |     0.11 % |
| 30 | manabox.app            |   172 |     0.09 % |
| 31 | channelfireball.com    |   171 |     0.09 % |
| 32 | edhrec.com             |   162 |     0.09 % |
| 33 | paupermtg.com          |   122 |     0.07 % |
| 34 | coolstuffinc.com       |   116 |     0.06 % |
| 35 | manatraders.com        |    93 |     0.05 % |
| 36 | mtgsearch.it           |    86 |     0.05 % |
| 37 | tcdecks.net            |    55 |     0.03 % |
| 38 | mtgstocks.com          |    53 |     0.03 % |
| 39 | commandersherald.com   |    43 |     0.02 % |
| 40 | manastack.com          |    40 |     0.02 % |
| 41 | mtgmeta.io             |    38 |     0.02 % |
| 42 | cyclesgaming.com       |    38 |     0.02 % |
| 43 | deckbox.org            |    34 |     0.02 % |
| 44 | cardhoarder.com        |    25 |     0.01 % |
| 45 | mtgvault.com           |    25 |     0.01 % |
| 46 | app.cardboard.live     |    19 |     0.01 % |
| 47 | draftsim.com           |    14 |     0.01 % |
| 48 | 17lands.com            |    11 |     0.01 % |
| 49 | magicblogs.de          |     4 |     0.00 % |
| 50 | mtgarena.pro           |     3 |     0.00 % |
| 51 | mtgotraders.com        |     1 |     0.00 % |
| 52 | playingmtg.com         |     1 |     0.00 % |
|  | TOTAL                  | 185968 | 100.00 %|
