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
    * Links to decklist services are scraped into Deck objects. 36 services are supported so far:
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
| 1  | commander       | 39434 |    38.68 % |
| 2  | standard        | 21981 |    21.56 % |
| 3  | modern          |  9570 |     9.39 % |
| 4  | pauper          |  6754 |     6.63 % |
| 5  | pioneer         |  5724 |     5.61 % |
| 6  | legacy          |  3463 |     3.40 % |
| 7  | brawl           |  2112 |     2.07 % |
| 8  | historic        |  1948 |     1.91 % |
| 9  | explorer        |  1745 |     1.71 % |
| 10 | undefined       |  1583 |     1.55 % |
| 11 | duel            |  1449 |     1.42 % |
| 12 | timeless        |  1420 |     1.39 % |
| 13 | paupercommander |  1302 |     1.28 % |
| 14 | premodern       |   767 |     0.75 % |
| 15 | irregular       |   706 |     0.69 % |
| 16 | vintage         |   685 |     0.67 % |
| 17 | alchemy         |   487 |     0.48 % |
| 18 | penny           |   268 |     0.26 % |
| 19 | standardbrawl   |   212 |     0.21 % |
| 20 | oathbreaker     |   197 |     0.19 % |
| 21 | gladiator       |    77 |     0.08 % |
| 22 | oldschool       |    35 |     0.03 % |
| 23 | future          |    22 |     0.02 % |
| 24 | predh           |     2 |     0.00 % |
|  | TOTAL           | 101943 | 100.00 %|

| No | Source | Count | Percentage |
|:---|:-----|------:|-----------:|
| 1  | moxfield.com           | 46932 |    46.04 % |
| 2  | arena.decklist         |  9550 |     9.37 % |
| 3  | aetherhub.com          |  7850 |     7.70 % |
| 4  | mtggoldfish.com        |  7778 |     7.63 % |
| 5  | mtgo.com               |  6744 |     6.62 % |
| 6  | archidekt.com          |  4176 |     4.10 % |
| 7  | mtgdecks.net           |  3005 |     2.95 % |
| 8  | tcgplayer.com          |  2179 |     2.14 % |
| 9  | mtga.untapped.gg       |  1942 |     1.90 % |
| 10 | melee.gg               |  1940 |     1.90 % |
| 11 | tappedout.net          |  1565 |     1.54 % |
| 12 | mtg.cardsrealm.com     |  1383 |     1.36 % |
| 13 | streamdecker.com       |  1232 |     1.21 % |
| 14 | mtgtop8.com            |  1171 |     1.15 % |
| 15 | magic.gg               |  1010 |     0.99 % |
| 16 | deckstats.net          |   533 |     0.52 % |
| 17 | mtgazone.com           |   432 |     0.42 % |
| 18 | hareruyamtg.com        |   352 |     0.35 % |
| 19 | pennydreadfulmagic.com |   250 |     0.25 % |
| 20 | scryfall.com           |   249 |     0.24 % |
| 21 | flexslot.gg            |   246 |     0.24 % |
| 22 | pauperwave.com         |   219 |     0.21 % |
| 23 | magic-ville.com        |   219 |     0.21 % |
| 24 | channelfireball.com    |   170 |     0.17 % |
| 25 | topdecked.com          |   157 |     0.15 % |
| 26 | old.starcitygames.com  |   151 |     0.15 % |
| 27 | manabox.app            |   122 |     0.12 % |
| 28 | manatraders.com        |    56 |     0.05 % |
| 29 | tcdecks.net            |    55 |     0.05 % |
| 30 | mtgstocks.com          |    44 |     0.04 % |
| 31 | manastack.com          |    39 |     0.04 % |
| 32 | mtgsearch.it           |    38 |     0.04 % |
| 33 | deckbox.org            |    28 |     0.03 % |
| 34 | paupermtg.com          |    26 |     0.03 % |
| 35 | cardhoarder.com        |    24 |     0.02 % |
| 36 | mtgarena.pro           |    22 |     0.02 % |
| 37 | cyclesgaming.com       |    20 |     0.02 % |
| 38 | app.cardboard.live     |    18 |     0.02 % |
| 39 | 17lands.com            |    11 |     0.01 % |
| 40 | magicblogs.de          |     4 |     0.00 % |
| 41 | mtgotraders.com        |     1 |     0.00 % |
|  | TOTAL                  | 101943 | 100.00 %|
