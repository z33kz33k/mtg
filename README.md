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
    * Links to decklist services are scraped into Deck objects. 35 services are supported so far:
        * [Aetherhub](https://aetherhub.com)
        * [Archidekt](https://archidekt.com)
        * [CardBoard Live](https://cardboard.live)
        * [Cardhoarder](https://www.cardhoarder.com)
        * [Cardsrealm](https://mtg.cardsrealm.com/en-us/)
        * [Deckbox](https://deckbox.org)
        * [Deckstats](https://deckstats.net)
        * [Flexslot](https://flexslot.gg)
        * [Goldfish](https://www.mtggoldfish.com)
        * [Hareruya](https://www.hareruyamtg.com/en/)
        * [LigaMagic](https://www.ligamagic.com.br/?view=home) _(with caveats)_
        * [Magic.gg](https://magic.gg)
        * [MagicVille](https://magic-ville.com/fr/index.php)
        * [ManaBox](https://manabox.app)
        * [ManaStack](https://manastack.com/home)
        * [Manatraders](https://www.manatraders.com)
        * [Melee.gg](https://melee.gg)
        * [Moxfield](https://www.moxfield.com)
        * [MTGArena.Pro](https://mtgarena.pro)
        * [MTGAZone](https://mtgazone.com)
        * [MTGDecks.net](https://mtgdecks.net)
        * [MTGO](https://www.mtgo.com/en/mtgo)
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
        * Deckbox users and events
        * Deckstats users
        * Flexslot users
        * Goldfish tournaments, players and articles
        * Hareruya events and players
        * LigaMagic events _(with caveats)_
        * MagicVille events and users
        * ManaStack users
        * Manatraders users
        * Magic.gg events
        * Melee.gg tournaments
        * Moxfield bookmarks, users and search results
        * MTGAZone articles and authors
        * MTGDecks.net tournaments
        * MTGO events
        * MTGStocks articles
        * MTGTop8 events
        * PennyDreadfulMagic competitions and users
        * StarCityGames events, players, articles and author's decks databases
        * Streamdecker users
        * TappedOut users, folders, and user folders
        * TCDecks events
        * TCGPlayer (old-site) players
        * TCGPlayer Infinite players (profile page), authors (search page) and events
        * [TopDeck.gg](https://topdeck.gg) brackets and profiles
        * Untapped profiles
* Assessing the meta:
    * Scraping Goldfish and MGTAZone for meta-decks (others in plans)
    * Scraping a singular Untapped meta-deck decklist page
* Exporting decks into a [Forge MTG](https://github.com/Card-Forge/forge) .dck format or Arena 
  decklist saved into a .txt file - with autogenerated, descriptive names based on scraped deck's 
  metadata
* Importing back into a Deck from those formats
* Export/import to other formats in plans
* Dumping decks, YT videos and channels to .json
* I compiled a list of **over 1.7k** YT channels that feature decks in their descriptions and successfully 
  scraped them (at least 25 videos deep) so this data only waits to be creatively used now!

### How it looks in a Google Sheet
![Most popular channels](assets/channels.jpg)

### Scraped decks breakdown
| No | Format | Count | Percentage |
|:---|:-----|------:|-----------:|
| 1  | commander       | 21423 |    30.27 % |
| 2  | standard        | 17519 |    24.75 % |
| 3  | modern          |  6138 |     8.67 % |
| 4  | pauper          |  5143 |     7.27 % |
| 5  | pioneer         |  4456 |     6.30 % |
| 6  | legacy          |  2961 |     4.18 % |
| 7  | brawl           |  1761 |     2.49 % |
| 8  | historic        |  1738 |     2.46 % |
| 9  | explorer        |  1558 |     2.20 % |
| 10 | duel            |  1327 |     1.87 % |
| 11 | undefined       |  1314 |     1.86 % |
| 12 | timeless        |  1301 |     1.84 % |
| 13 | paupercommander |  1121 |     1.58 % |
| 14 | premodern       |   692 |     0.98 % |
| 15 | vintage         |   610 |     0.86 % |
| 16 | irregular       |   605 |     0.85 % |
| 17 | alchemy         |   423 |     0.60 % |
| 18 | penny           |   267 |     0.38 % |
| 19 | standardbrawl   |   194 |     0.27 % |
| 20 | oathbreaker     |   106 |     0.15 % |
| 21 | gladiator       |    77 |     0.11 % |
| 22 | oldschool       |    34 |     0.05 % |
| 23 | future          |    16 |     0.02 % |
|  | TOTAL           | 70784 | 100.00 %|

| No | Source | Count | Percentage |
|:---|:-----|------:|-----------:|
| 1  | moxfield.com           | 27997 |    39.55 % |
| 2  | arena.decklist         |  7914 |    11.18 % |
| 3  | aetherhub.com          |  7014 |     9.91 % |
| 4  | mtggoldfish.com        |  6741 |     9.52 % |
| 5  | mtgo.com               |  3955 |     5.59 % |
| 6  | archidekt.com          |  3295 |     4.66 % |
| 7  | mtga.untapped.gg       |  1614 |     2.28 % |
| 8  | melee.gg               |  1519 |     2.15 % |
| 9  | tappedout.net          |  1512 |     2.14 % |
| 10 | mtgdecks.net           |  1505 |     2.13 % |
| 11 | mtgtop8.com            |  1050 |     1.48 % |
| 12 | streamdecker.com       |  1039 |     1.47 % |
| 13 | magic.gg               |  1010 |     1.43 % |
| 14 | tcgplayer.com          |   988 |     1.40 % |
| 15 | mtg.cardsrealm.com     |   805 |     1.14 % |
| 16 | deckstats.net          |   504 |     0.71 % |
| 17 | mtgazone.com           |   407 |     0.57 % |
| 18 | hareruyamtg.com        |   318 |     0.45 % |
| 19 | pennydreadfulmagic.com |   249 |     0.35 % |
| 20 | flexslot.gg            |   242 |     0.34 % |
| 21 | magic-ville.com        |   211 |     0.30 % |
| 22 | scryfall.com           |   206 |     0.29 % |
| 23 | old.starcitygames.com  |   141 |     0.20 % |
| 24 | topdecked.com          |   139 |     0.20 % |
| 25 | manabox.app            |   109 |     0.15 % |
| 26 | manatraders.com        |    55 |     0.08 % |
| 27 | tcdecks.net            |    54 |     0.08 % |
| 28 | mtgstocks.com          |    41 |     0.06 % |
| 29 | manastack.com          |    38 |     0.05 % |
| 30 | deckbox.org            |    27 |     0.04 % |
| 31 | paupermtg.com          |    24 |     0.03 % |
| 32 | mtgarena.pro           |    22 |     0.03 % |
| 33 | cardhoarder.com        |    22 |     0.03 % |
| 34 | app.cardboard.live     |    16 |     0.02 % |
| 35 | mtgotraders.com        |     1 |     0.00 % |
|  | TOTAL                  | 70784 | 100.00 %|
