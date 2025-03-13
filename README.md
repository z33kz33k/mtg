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
    * Links to decklist sites are scraped into Deck objects. 40 sites are supported so far:
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
    * Other decklist sites are in plans (but, it does seem like I've pretty much exhausted the 
      possibilities already :))
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
        * Draftsim articles
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
* I compiled a list of **over 2k** YT channels that feature decks in their descriptions and successfully 
  scraped them (at least 25 videos deep) so this data only waits to be creatively used now!

### How it looks in a Google Sheet
![Most popular channels](assets/channels.jpg)

### Scraped decks breakdown
| No | Format | Count | Percentage |
|:---|:-----|------:|-----------:|
| 1  | commander       | 45845 |    39.27 % |
| 2  | standard        | 25504 |    21.84 % |
| 3  | modern          | 11098 |     9.51 % |
| 4  | pauper          |  7214 |     6.18 % |
| 5  | pioneer         |  6527 |     5.59 % |
| 6  | legacy          |  3743 |     3.21 % |
| 7  | brawl           |  2542 |     2.18 % |
| 8  | historic        |  2110 |     1.81 % |
| 9  | explorer        |  1918 |     1.64 % |
| 10 | undefined       |  1760 |     1.51 % |
| 11 | paupercommander |  1650 |     1.41 % |
| 12 | duel            |  1520 |     1.30 % |
| 13 | timeless        |  1506 |     1.29 % |
| 14 | premodern       |   834 |     0.71 % |
| 15 | irregular       |   787 |     0.67 % |
| 16 | vintage         |   749 |     0.64 % |
| 17 | alchemy         |   535 |     0.46 % |
| 18 | penny           |   284 |     0.24 % |
| 19 | oathbreaker     |   250 |     0.21 % |
| 20 | standardbrawl   |   226 |     0.19 % |
| 21 | gladiator       |    85 |     0.07 % |
| 22 | oldschool       |    36 |     0.03 % |
| 23 | future          |    26 |     0.02 % |
| 24 | predh           |     4 |     0.00 % |
|  | TOTAL           | 116753 | 100.00 %|

| No | Source | Count | Percentage |
|:---|:-----|------:|-----------:|
| 1  | moxfield.com           | 54040 |    46.29 % |
| 2  | arena.decklist         | 10689 |     9.16 % |
| 3  | mtgo.com               |  8921 |     7.64 % |
| 4  | mtggoldfish.com        |  8720 |     7.47 % |
| 5  | aetherhub.com          |  8461 |     7.25 % |
| 6  | archidekt.com          |  4841 |     4.15 % |
| 7  | mtgdecks.net           |  3292 |     2.82 % |
| 8  | tcgplayer.com          |  2210 |     1.89 % |
| 9  | mtga.untapped.gg       |  2208 |     1.89 % |
| 10 | melee.gg               |  2151 |     1.84 % |
| 11 | mtg.cardsrealm.com     |  1654 |     1.42 % |
| 12 | tappedout.net          |  1598 |     1.37 % |
| 13 | magic.gg               |  1358 |     1.16 % |
| 14 | streamdecker.com       |  1331 |     1.14 % |
| 15 | mtgtop8.com            |  1235 |     1.06 % |
| 16 | deckstats.net          |   539 |     0.46 % |
| 17 | mtgazone.com           |   440 |     0.38 % |
| 18 | hareruyamtg.com        |   395 |     0.34 % |
| 19 | flexslot.gg            |   276 |     0.24 % |
| 20 | pennydreadfulmagic.com |   266 |     0.23 % |
| 21 | scryfall.com           |   257 |     0.22 % |
| 22 | pauperwave.com         |   227 |     0.19 % |
| 23 | magic.wizards.com      |   211 |     0.18 % |
| 24 | magic-ville.com        |   186 |     0.16 % |
| 25 | starcitygames.com      |   172 |     0.15 % |
| 26 | channelfireball.com    |   170 |     0.15 % |
| 27 | topdecked.com          |   165 |     0.14 % |
| 28 | edhrec.com             |   147 |     0.13 % |
| 29 | manabox.app            |   130 |     0.11 % |
| 30 | manatraders.com        |    58 |     0.05 % |
| 31 | tcdecks.net            |    55 |     0.05 % |
| 32 | mtgstocks.com          |    50 |     0.04 % |
| 33 | mtgcircle.com          |    49 |     0.04 % |
| 34 | mtgsearch.it           |    44 |     0.04 % |
| 35 | manastack.com          |    39 |     0.03 % |
| 36 | deckbox.org            |    30 |     0.03 % |
| 37 | paupermtg.com          |    28 |     0.02 % |
| 38 | cardhoarder.com        |    25 |     0.02 % |
| 39 | mtgarena.pro           |    22 |     0.02 % |
| 40 | cyclesgaming.com       |    22 |     0.02 % |
| 41 | app.cardboard.live     |    19 |     0.02 % |
| 42 | 17lands.com            |    11 |     0.01 % |
| 43 | draftsim.com           |     6 |     0.01 % |
| 44 | magicblogs.de          |     4 |     0.00 % |
| 45 | mtgotraders.com        |     1 |     0.00 % |
|  | TOTAL                  | 116753 | 100.00 %|
