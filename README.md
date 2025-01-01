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
    * Links to decklist services are scraped into Deck objects. 33 services are supported so far:
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
    * Both Untapped decklist types featured in YT videos are supported: regular deck and profile deck
    * Both old TCGPlayer site and TCGPlayer Infinite are supported
    * Both international and native Hareruya sites are supported 
    * Sites that need it are scraped using [Selenium](https://github.com/SeleniumHQ/Selenium)
    * LigaMagic is the only sore spot that demands from me investing in scraping APIs to bypass 
      their CloudFlare protection and be fully supported (anyway, the logic to scrape them is already in place)
    * All those mentioned above work even if they are behind shortener links and need unshortening first
    * Text decklists in links to pastebin-like services (like [Amazonian](https://www.youtube.com/@Amazonian) does) work too
    * If nothing is found in the video's description, then the author's comments are parsed
    * Deck's name and format are derived (from a video's title, description and keywords) if not readily available
    * Foreign cards and other that cannot be found in the downloaded Scryfall bulk data are looked 
      up with queries to the Scryfall API
    * Individual decklist URLs are extracted from container pages and further processed for decks. 
      These include:
        * Aetherhub users and events
        * Archidekt folders and users
        * Cardsrealm profiles, folders, tournaments and articles
        * Deckbox users and events
        * Deckstats users
        * Flexslot users
        * Goldfish tournaments and players
        * Hareruya events and players
        * LigaMagic events _(with caveats)_
        * MagicVille events and users
        * ManaStack users
        * Manatraders users
        * Melee.gg tournaments
        * Moxfield bookmarks and users
        * MTGDecks.net tournaments
        * MTGTop8 events
        * PennyDreadfulMagic competitions and users
        * StarCityGames events, articles and author's decks databases
        * Streamdecker users
        * TappedOut users, folders, and user folders
        * TCDecks events
        * TCGPlayer (old-site) players
        * TCGPlayer Infinite players (profile page), authors (search page) and events
        * Untapped profiles
    * Other, non-URL based container pages are processed for decks, too. These include:
        * MGTO events
* Assessing the meta:
    * Scraping Goldfish and MGTAZone for meta-decks (others in plans)
    * Scraping a singular Untapped meta-deck decklist page
* Exporting decks into a [Forge MTG](https://github.com/Card-Forge/forge) .dck format or Arena 
  decklist saved into a .txt file - with autogenerated, descriptive names based on scraped deck's 
  metadata
* Importing back into a Deck from those formats
* Export/import to other formats in plans
* Dumping decks, YT videos and channels to .json
* I compiled a list of **over 1.6k** YT channels that feature decks in their descriptions and successfully 
  scraped them (at least 25 videos deep) so this data only waits to be creatively used now!

### How it looks in a Google Sheet
![Most popular channels](assets/channels.jpg)

### Scraped decks breakdown
| No | Format | Count | Percentage |
|:---|:-----|------:|-----------:|
| 1  | commander       | 17271 |    29.78 % |
| 2  | standard        | 14087 |    24.29 % |
| 3  | pauper          |  4739 |     8.17 % |
| 4  | modern          |  4635 |     7.99 % |
| 5  | pioneer         |  3525 |     6.08 % |
| 6  | legacy          |  2708 |     4.67 % |
| 7  | historic        |  1510 |     2.60 % |
| 8  | brawl           |  1499 |     2.58 % |
| 9  | explorer        |  1379 |     2.38 % |
| 10 | duel            |  1230 |     2.12 % |
| 11 | undefined       |  1209 |     2.08 % |
| 12 | timeless        |  1187 |     2.05 % |
| 13 | premodern       |   584 |     1.01 % |
| 14 | vintage         |   548 |     0.94 % |
| 15 | paupercommander |   467 |     0.81 % |
| 16 | irregular       |   448 |     0.77 % |
| 17 | alchemy         |   364 |     0.63 % |
| 18 | penny           |   278 |     0.48 % |
| 19 | standardbrawl   |   184 |     0.32 % |
| 20 | oathbreaker     |    70 |     0.12 % |
| 21 | gladiator       |    44 |     0.08 % |
| 22 | oldschool       |    19 |     0.03 % |
| 23 | future          |    15 |     0.03 % |
|  | TOTAL           | 58000 | 100.00 %|

| No | Source | Count | Percentage |
|:---|:-----|------:|-----------:|
| 1  | moxfield.com           | 21887 |    37.74 % |
| 2  | arena.decklist         |  7152 |    12.33 % |
| 3  | aetherhub.com          |  6560 |    11.31 % |
| 4  | mtggoldfish.com        |  5845 |    10.08 % |
| 5  | archidekt.com          |  2995 |     5.16 % |
| 6  | mtgo.com               |  2238 |     3.86 % |
| 7  | mtga.untapped.gg       |  1429 |     2.46 % |
| 8  | tappedout.net          |  1318 |     2.27 % |
| 9  | mtgdecks.net           |  1238 |     2.13 % |
| 10 | melee.gg               |  1219 |     2.10 % |
| 11 | streamdecker.com       |  1058 |     1.82 % |
| 12 | mtgtop8.com            |  1039 |     1.79 % |
| 13 | tcgplayer.com          |   924 |     1.59 % |
| 14 | mtg.cardsrealm.com     |   684 |     1.18 % |
| 15 | deckstats.net          |   508 |     0.88 % |
| 16 | hareruyamtg.com        |   285 |     0.49 % |
| 17 | pennydreadfulmagic.com |   249 |     0.43 % |
| 18 | scryfall.com           |   199 |     0.34 % |
| 19 | mtgazone.com           |   193 |     0.33 % |
| 20 | magic-ville.com        |   187 |     0.32 % |
| 21 | flexslot.gg            |   186 |     0.32 % |
| 22 | topdecked.com          |   131 |     0.23 % |
| 23 | old.starcitygames.com  |   117 |     0.20 % |
| 24 | manabox.app            |   105 |     0.18 % |
| 25 | manatraders.com        |    55 |     0.09 % |
| 26 | tcdecks.net            |    54 |     0.09 % |
| 27 | manastack.com          |    38 |     0.07 % |
| 28 | deckbox.org            |    27 |     0.05 % |
| 29 | mtgarena.pro           |    23 |     0.04 % |
| 30 | paupermtg.com          |    22 |     0.04 % |
| 31 | cardhoarder.com        |    20 |     0.03 % |
| 32 | app.cardboard.live     |    14 |     0.02 % |
| 33 | mtgotraders.com        |     1 |     0.00 % |
|  | TOTAL                  | 58000 | 100.00 %|
