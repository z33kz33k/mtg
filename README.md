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
* Scraping YouTube channels for decklist-featuring video descriptions (or comments) - using no less than 
  four Python libraries to avoid bothering with Google APIs: 
    * [scrapetube](https://github.com/dermasmid/scrapetube),
    * [pytubefix](https://github.com/JuanBindez/pytubefix),
    * [youtubesearchpython](https://github.com/alexmercerind/youtube-search-python), 
    * [youtube-comment-downloader](https://github.com/egbertbouman/youtube-comment-downloader) 
* Parsing those descriptions (or comments) for decks:    
    * Text decklists in Arena/MTGO format pasted into video descriptions are parsed into Deck objects
    * Links to decklist sites are scraped into Deck objects. 43 sites are supported so far:
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
        * [TopDecked](https://www.topdecked.com)
        * [Untapped](https://mtga.untapped.gg) 
    * 3 more decklist sites in plans 
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
        * [Cardmarket](https://www.cardmarket.com/) articles 
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
        * Melee.gg profiles and tournaments
        * Moxfield bookmarks, users and search results
        * MTGAZone articles and authors
        * MTGCircle articles
        * MTGDecks.net tournaments and articles
        * MTGMeta.io articles and tournaments _(defunct, scraped via Wayback Machine)_
        * [MTGO](https://www.mtgo.com/en/mtgo) events
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
    * 80 container pages in total with 15 more in plans
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
* I compiled a list of **over 2.1k** YT channels that feature decks in their descriptions and successfully 
  scraped them (at least 25 videos deep) so this data only waits to be creatively used now!

### How it looks in a Google Sheet
![Most popular channels](assets/channels.jpg)

### Scraped decks breakdown
| No | Format | Count | Percentage |
|:---|:-----|------:|-----------:|
| 1  | commander       | 54193 |    39.78 % |
| 2  | standard        | 28906 |    21.22 % |
| 3  | modern          | 14021 |    10.29 % |
| 4  | pauper          |  8190 |     6.01 % |
| 5  | pioneer         |  7706 |     5.66 % |
| 6  | legacy          |  4267 |     3.13 % |
| 7  | brawl           |  2874 |     2.11 % |
| 8  | historic        |  2354 |     1.73 % |
| 9  | explorer        |  2202 |     1.62 % |
| 10 | paupercommander |  1932 |     1.42 % |
| 11 | undefined       |  1932 |     1.42 % |
| 12 | duel            |  1665 |     1.22 % |
| 13 | timeless        |  1637 |     1.20 % |
| 14 | premodern       |   911 |     0.67 % |
| 15 | irregular       |   910 |     0.67 % |
| 16 | vintage         |   827 |     0.61 % |
| 17 | alchemy         |   655 |     0.48 % |
| 18 | oathbreaker     |   336 |     0.25 % |
| 19 | penny           |   298 |     0.22 % |
| 20 | standardbrawl   |   250 |     0.18 % |
| 21 | gladiator       |    86 |     0.06 % |
| 22 | oldschool       |    48 |     0.04 % |
| 23 | future          |    30 |     0.02 % |
| 24 | predh           |     5 |     0.00 % |
|  | TOTAL           | 136235 | 100.00 %|

| No | Source | Count | Percentage |
|:---|:-----|------:|-----------:|
| 1  | moxfield.com           | 63770 |    46.81 % |
| 2  | arena.decklist         | 12141 |     8.91 % |
| 3  | mtgo.com               | 10881 |     7.99 % |
| 4  | mtggoldfish.com        |  9628 |     7.07 % |
| 5  | aetherhub.com          |  9183 |     6.74 % |
| 6  | archidekt.com          |  5217 |     3.83 % |
| 7  | mtgdecks.net           |  4322 |     3.17 % |
| 8  | melee.gg               |  2552 |     1.87 % |
| 9  | mtga.untapped.gg       |  2550 |     1.87 % |
| 10 | tcgplayer.com          |  2315 |     1.70 % |
| 11 | mtg.cardsrealm.com     |  2159 |     1.58 % |
| 12 | tappedout.net          |  1646 |     1.21 % |
| 13 | streamdecker.com       |  1468 |     1.08 % |
| 14 | magic.gg               |  1421 |     1.04 % |
| 15 | mtgtop8.com            |  1307 |     0.96 % |
| 16 | mtgazone.com           |   697 |     0.51 % |
| 17 | deckstats.net          |   563 |     0.41 % |
| 18 | starcitygames.com      |   446 |     0.33 % |
| 19 | hareruyamtg.com        |   424 |     0.31 % |
| 20 | mtgcircle.com          |   365 |     0.27 % |
| 21 | flexslot.gg            |   349 |     0.26 % |
| 22 | magic.wizards.com      |   314 |     0.23 % |
| 23 | pennydreadfulmagic.com |   279 |     0.20 % |
| 24 | pauperwave.com         |   277 |     0.20 % |
| 25 | scryfall.com           |   268 |     0.20 % |
| 26 | cardmarket.com         |   256 |     0.19 % |
| 27 | magic-ville.com        |   189 |     0.14 % |
| 28 | topdecked.com          |   177 |     0.13 % |
| 29 | channelfireball.com    |   171 |     0.13 % |
| 30 | edhrec.com             |   150 |     0.11 % |
| 31 | manabox.app            |   149 |     0.11 % |
| 32 | paupermtg.com          |    96 |     0.07 % |
| 33 | manatraders.com        |    81 |     0.06 % |
| 34 | mtgsearch.it           |    61 |     0.04 % |
| 35 | tcdecks.net            |    55 |     0.04 % |
| 36 | mtgstocks.com          |    52 |     0.04 % |
| 37 | manastack.com          |    40 |     0.03 % |
| 38 | mtgmeta.io             |    38 |     0.03 % |
| 39 | deckbox.org            |    30 |     0.02 % |
| 40 | cyclesgaming.com       |    30 |     0.02 % |
| 41 | cardhoarder.com        |    25 |     0.02 % |
| 42 | mtgvault.com           |    25 |     0.02 % |
| 43 | mtgarena.pro           |    22 |     0.02 % |
| 44 | app.cardboard.live     |    19 |     0.01 % |
| 45 | 17lands.com            |    11 |     0.01 % |
| 46 | draftsim.com           |    10 |     0.01 % |
| 47 | magicblogs.de          |     4 |     0.00 % |
| 48 | mtgotraders.com        |     1 |     0.00 % |
| 49 | playingmtg.com         |     1 |     0.00 % |
|  | TOTAL                  | 136235 | 100.00 %|
