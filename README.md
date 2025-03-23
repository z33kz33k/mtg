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

Now, the main focus is `decks` package and `yt` module (parsing data on youtubers' decks from 
YT videos descriptions).

### What works

* Scryfall data management via downloading bulk data with 
  [scrython](https://github.com/NandaScott/Scrython) and wrapping it in convenient abstractions
* Scraping YouTube channels for videos with decklists in descriptions (or comments) - using no less than 
  four Python libraries to avoid bothering with Google APIs: 
    * [scrapetube](https://github.com/dermasmid/scrapetube),
    * [pytubefix](https://github.com/JuanBindez/pytubefix),
    * [youtubesearchpython](https://github.com/alexmercerind/youtube-search-python), 
    * [youtube-comment-downloader](https://github.com/egbertbouman/youtube-comment-downloader) 
* Scraping YT videos' descriptions (or comments) for decks:    
    * Text decklists in Arena/MTGO format pasted into video descriptions are parsed into Deck objects
    * Links to decklist sites are scraped into Deck objects. 41 sites are supported so far:
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
    * 5 more decklist sites in plans 
    * Both Aetherhub decklist types featured in YT videos are supported: regular deck and write-up deck
    * Both Archidekt decklist types featured in YT videos are supported: regular deck and snapshot deck
    * Both EDHREC decklist types featured in YT videos are supported: preview deck and average deck
    * Both MTGCircle decklist types featured in YT videos are supported: video deck and regular deck
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
        * ChannelFireball players, articles and authors
        * [CyclesGaming](https://cyclesgaming.com) articles
        * Deckbox users and events
        * Deckstats users
        * Draftsim articles and authors
        * EDHREC articles and authors
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
        * Melee.gg tournaments
        * Moxfield bookmarks, users and search results
        * MTGAZone articles and authors
        * MTGCircle articles
        * MTGDecks.net tournaments
        * MTGMeta.io articles and tournaments _(defunct, scraped via Wayback Machine)_
        * [MTGO](https://www.mtgo.com/en/mtgo) events
        * MTGStocks articles
        * MTGTop8 events
        * [Pauperwave](https://www.pauperwave.com) articles
        * PennyDreadfulMagic competitions and users
        * StarCityGames events, players, articles and author's decks databases
        * Streamdecker users
        * TappedOut users, folders, and user folders
        * TCDecks events
        * TCGPlayer (old-site) players
        * TCGPlayer Infinite players, authors, author searches, author deck panes, events and articles
        * [TopDeck.gg](https://topdeck.gg) brackets and profiles
        * Untapped profiles
        * [WotC (official MTG site)](https://magic.wizards.com/en) articles
    * 20 more container pages in plans
* Assessing the meta:
    * Scraping Goldfish and MGTAZone for meta-decks (others in plans)
    * Scraping a singular Untapped meta-deck decklist page
* Exporting decks into [XMage](https://xmage.today) .dck format, [Forge MTG](https://github.com/Card-Forge/forge) .dck format or Arena 
  decklist saved into a .txt file - with autogenerated, descriptive names based on scraped deck's 
  metadata
* Importing back into a Deck from those formats
* Export/import to other formats in plans
* Dumping decks, YT videos and channels to .json
* Semi-automatic discovery of new channels
* I compiled a list of **over 2k** YT channels that feature decks in their descriptions and successfully 
  scraped them (at least 25 videos deep) so this data only waits to be creatively used now!

### How it looks in a Google Sheet
![Most popular channels](assets/channels.jpg)

### Scraped decks breakdown
| No | Format | Count | Percentage |
|:---|:-----|------:|-----------:|
| 1  | commander       | 49566 |    39.22 % |
| 2  | standard        | 27053 |    21.41 % |
| 3  | modern          | 13071 |    10.34 % |
| 4  | pauper          |  7545 |     5.97 % |
| 5  | pioneer         |  7273 |     5.75 % |
| 6  | legacy          |  3995 |     3.16 % |
| 7  | brawl           |  2682 |     2.12 % |
| 8  | historic        |  2286 |     1.81 % |
| 9  | explorer        |  2091 |     1.65 % |
| 10 | undefined       |  1835 |     1.45 % |
| 11 | paupercommander |  1761 |     1.39 % |
| 12 | duel            |  1586 |     1.25 % |
| 13 | timeless        |  1527 |     1.21 % |
| 14 | irregular       |   876 |     0.69 % |
| 15 | premodern       |   855 |     0.68 % |
| 16 | vintage         |   785 |     0.62 % |
| 17 | alchemy         |   601 |     0.48 % |
| 18 | oathbreaker     |   310 |     0.25 % |
| 19 | penny           |   297 |     0.23 % |
| 20 | standardbrawl   |   234 |     0.19 % |
| 21 | gladiator       |    85 |     0.07 % |
| 22 | oldschool       |    40 |     0.03 % |
| 23 | future          |    27 |     0.02 % |
| 24 | predh           |     5 |     0.00 % |
|  | TOTAL           | 126386 | 100.00 %|

| No | Source | Count | Percentage |
|:---|:-----|------:|-----------:|
| 1  | moxfield.com           | 58214 |    46.06 % |
| 2  | arena.decklist         | 11243 |     8.90 % |
| 3  | mtgo.com               |  9985 |     7.90 % |
| 4  | mtggoldfish.com        |  9312 |     7.37 % |
| 5  | aetherhub.com          |  8775 |     6.94 % |
| 6  | archidekt.com          |  5045 |     3.99 % |
| 7  | mtgdecks.net           |  4246 |     3.36 % |
| 8  | melee.gg               |  2497 |     1.98 % |
| 9  | mtga.untapped.gg       |  2384 |     1.89 % |
| 10 | tcgplayer.com          |  2270 |     1.80 % |
| 11 | mtg.cardsrealm.com     |  1811 |     1.43 % |
| 12 | tappedout.net          |  1613 |     1.28 % |
| 13 | streamdecker.com       |  1416 |     1.12 % |
| 14 | magic.gg               |  1392 |     1.10 % |
| 15 | mtgtop8.com            |  1283 |     1.02 % |
| 16 | mtgazone.com           |   688 |     0.54 % |
| 17 | deckstats.net          |   554 |     0.44 % |
| 18 | starcitygames.com      |   434 |     0.34 % |
| 19 | hareruyamtg.com        |   406 |     0.32 % |
| 20 | flexslot.gg            |   309 |     0.24 % |
| 21 | pennydreadfulmagic.com |   279 |     0.22 % |
| 22 | scryfall.com           |   260 |     0.21 % |
| 23 | pauperwave.com         |   228 |     0.18 % |
| 24 | magic.wizards.com      |   224 |     0.18 % |
| 25 | magic-ville.com        |   187 |     0.15 % |
| 26 | channelfireball.com    |   171 |     0.14 % |
| 27 | topdecked.com          |   167 |     0.13 % |
| 28 | mtgcircle.com          |   164 |     0.13 % |
| 29 | edhrec.com             |   147 |     0.12 % |
| 30 | manabox.app            |   139 |     0.11 % |
| 31 | paupermtg.com          |    96 |     0.08 % |
| 32 | manatraders.com        |    58 |     0.05 % |
| 33 | tcdecks.net            |    55 |     0.04 % |
| 34 | mtgsearch.it           |    55 |     0.04 % |
| 35 | mtgstocks.com          |    52 |     0.04 % |
| 36 | manastack.com          |    40 |     0.03 % |
| 37 | mtgmeta.io             |    38 |     0.03 % |
| 38 | deckbox.org            |    30 |     0.02 % |
| 39 | cyclesgaming.com       |    27 |     0.02 % |
| 40 | cardhoarder.com        |    25 |     0.02 % |
| 41 | mtgarena.pro           |    22 |     0.02 % |
| 42 | app.cardboard.live     |    19 |     0.02 % |
| 43 | 17lands.com            |    11 |     0.01 % |
| 44 | draftsim.com           |    10 |     0.01 % |
| 45 | magicblogs.de          |     4 |     0.00 % |
| 46 | mtgotraders.com        |     1 |     0.00 % |
|  | TOTAL                  | 126386 | 100.00 %|
