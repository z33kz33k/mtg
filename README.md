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
    * Links to decklist services are scraped into Deck objects. 37 services are supported so far:
        * [17Lands](https://www.17lands.com)
        * [Aetherhub](https://aetherhub.com)
        * [Archidekt](https://archidekt.com)
        * [CardBoard Live](https://cardboard.live)
        * [Cardhoarder](https://www.cardhoarder.com)
        * [Cardsrealm](https://mtg.cardsrealm.com/en-us/)
        * [ChannelFireball](https://www.channelfireball.com)
        * [Deckbox](https://deckbox.org)
        * [Deckstats](https://deckstats.net)
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
        * [MTGDecks.net](https://mtgdecks.net)
        * [MTGJSON](https://mtgjson.com)
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
    * Both Archidekt decklist types featured in YT videos are supported: regular deck and snapshot deck
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
        * MTGDecks.net tournaments
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
* Assessing the meta:
    * Scraping Goldfish and MGTAZone for meta-decks (others in plans)
    * Scraping a singular Untapped meta-deck decklist page
* Exporting decks into [XMage](https://xmage.today) .dck format, [Forge MTG](https://github.com/Card-Forge/forge) .dck format or Arena 
  decklist saved into a .txt file - with autogenerated, descriptive names based on scraped deck's 
  metadata
* Importing back into a Deck from those formats
* Export/import to other formats in plans
* Dumping decks, YT videos and channels to .json
* I compiled a list of **over 1.9k** YT channels that feature decks in their descriptions and successfully 
  scraped them (at least 25 videos deep) so this data only waits to be creatively used now!

### How it looks in a Google Sheet
![Most popular channels](assets/channels.jpg)

### Scraped decks breakdown
| No | Format | Count | Percentage |
|:---|:-----|------:|-----------:|
| 1  | commander       | 42003 |    38.98 % |
| 2  | standard        | 23340 |    21.66 % |
| 3  | modern          | 10121 |     9.39 % |
| 4  | pauper          |  6873 |     6.38 % |
| 5  | pioneer         |  6005 |     5.57 % |
| 6  | legacy          |  3550 |     3.29 % |
| 7  | brawl           |  2375 |     2.20 % |
| 8  | historic        |  2024 |     1.88 % |
| 9  | explorer        |  1777 |     1.65 % |
| 10 | undefined       |  1633 |     1.52 % |
| 11 | paupercommander |  1566 |     1.45 % |
| 12 | duel            |  1464 |     1.36 % |
| 13 | timeless        |  1448 |     1.34 % |
| 14 | premodern       |   792 |     0.74 % |
| 15 | irregular       |   719 |     0.67 % |
| 16 | vintage         |   702 |     0.65 % |
| 17 | alchemy         |   498 |     0.46 % |
| 18 | penny           |   268 |     0.25 % |
| 19 | oathbreaker     |   227 |     0.21 % |
| 20 | standardbrawl   |   217 |     0.20 % |
| 21 | gladiator       |    81 |     0.08 % |
| 22 | oldschool       |    35 |     0.03 % |
| 23 | future          |    23 |     0.02 % |
| 24 | predh           |     2 |     0.00 % |
|  | TOTAL           | 107743 | 100.00 %|

| No | Source | Count | Percentage |
|:---|:-----|------:|-----------:|
| 1  | moxfield.com           | 50009 |    46.42 % |
| 2  | arena.decklist         |  9882 |     9.17 % |
| 3  | mtggoldfish.com        |  8130 |     7.55 % |
| 4  | aetherhub.com          |  8029 |     7.45 % |
| 5  | mtgo.com               |  7417 |     6.88 % |
| 6  | archidekt.com          |  4412 |     4.09 % |
| 7  | mtgdecks.net           |  3110 |     2.89 % |
| 8  | tcgplayer.com          |  2188 |     2.03 % |
| 9  | melee.gg               |  2034 |     1.89 % |
| 10 | mtga.untapped.gg       |  2028 |     1.88 % |
| 11 | tappedout.net          |  1564 |     1.45 % |
| 12 | mtg.cardsrealm.com     |  1426 |     1.32 % |
| 13 | magic.gg               |  1358 |     1.26 % |
| 14 | streamdecker.com       |  1260 |     1.17 % |
| 15 | mtgtop8.com            |  1173 |     1.09 % |
| 16 | deckstats.net          |   522 |     0.48 % |
| 17 | mtgazone.com           |   433 |     0.40 % |
| 18 | hareruyamtg.com        |   364 |     0.34 % |
| 19 | flexslot.gg            |   262 |     0.24 % |
| 20 | scryfall.com           |   253 |     0.23 % |
| 21 | pennydreadfulmagic.com |   250 |     0.23 % |
| 22 | pauperwave.com         |   227 |     0.21 % |
| 23 | magic-ville.com        |   219 |     0.20 % |
| 24 | magic.wizards.com      |   188 |     0.17 % |
| 25 | channelfireball.com    |   170 |     0.16 % |
| 26 | old.starcitygames.com  |   161 |     0.15 % |
| 27 | topdecked.com          |   158 |     0.15 % |
| 28 | manabox.app            |   125 |     0.12 % |
| 29 | manatraders.com        |    56 |     0.05 % |
| 30 | tcdecks.net            |    55 |     0.05 % |
| 31 | mtgstocks.com          |    45 |     0.04 % |
| 32 | manastack.com          |    39 |     0.04 % |
| 33 | mtgsearch.it           |    39 |     0.04 % |
| 34 | deckbox.org            |    29 |     0.03 % |
| 35 | paupermtg.com          |    26 |     0.02 % |
| 36 | cardhoarder.com        |    24 |     0.02 % |
| 37 | mtgarena.pro           |    22 |     0.02 % |
| 38 | cyclesgaming.com       |    21 |     0.02 % |
| 39 | app.cardboard.live     |    19 |     0.02 % |
| 40 | 17lands.com            |    11 |     0.01 % |
| 41 | magicblogs.de          |     4 |     0.00 % |
| 42 | mtgotraders.com        |     1 |     0.00 % |
|  | TOTAL                  | 107743 | 100.00 %|
