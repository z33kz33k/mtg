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
    * Links to decklist services are scraped into Deck objects. 34 services are supported so far:
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
        * Magic.gg events
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
| 1  | commander       | 17679 |    29.00 % |
| 2  | standard        | 15436 |    25.32 % |
| 3  | modern          |  5138 |     8.43 % |
| 4  | pauper          |  4906 |     8.05 % |
| 5  | pioneer         |  3713 |     6.09 % |
| 6  | legacy          |  2721 |     4.46 % |
| 7  | historic        |  1600 |     2.62 % |
| 8  | brawl           |  1535 |     2.52 % |
| 9  | explorer        |  1420 |     2.33 % |
| 10 | undefined       |  1269 |     2.08 % |
| 11 | duel            |  1236 |     2.03 % |
| 12 | timeless        |  1221 |     2.00 % |
| 13 | premodern       |   589 |     0.97 % |
| 14 | vintage         |   549 |     0.90 % |
| 15 | paupercommander |   472 |     0.77 % |
| 16 | irregular       |   461 |     0.76 % |
| 17 | alchemy         |   374 |     0.61 % |
| 18 | penny           |   278 |     0.46 % |
| 19 | standardbrawl   |   186 |     0.31 % |
| 20 | gladiator       |    76 |     0.12 % |
| 21 | oathbreaker     |    73 |     0.12 % |
| 22 | oldschool       |    20 |     0.03 % |
| 23 | future          |    15 |     0.02 % |
|  | TOTAL           | 60967 | 100.00 %|

| No | Source | Count | Percentage |
|:---|:-----|------:|-----------:|
| 1  | moxfield.com           | 22756 |    37.33 % |
| 2  | arena.decklist         |  7290 |    11.96 % |
| 3  | aetherhub.com          |  6617 |    10.85 % |
| 4  | mtggoldfish.com        |  6011 |     9.86 % |
| 5  | archidekt.com          |  3004 |     4.93 % |
| 6  | mtgo.com               |  2814 |     4.62 % |
| 7  | mtga.untapped.gg       |  1474 |     2.42 % |
| 8  | tappedout.net          |  1318 |     2.16 % |
| 9  | mtgdecks.net           |  1287 |     2.11 % |
| 10 | melee.gg               |  1280 |     2.10 % |
| 11 | streamdecker.com       |  1072 |     1.76 % |
| 12 | mtgtop8.com            |  1040 |     1.71 % |
| 13 | magic.gg               |   957 |     1.57 % |
| 14 | tcgplayer.com          |   927 |     1.52 % |
| 15 | mtg.cardsrealm.com     |   684 |     1.12 % |
| 16 | deckstats.net          |   509 |     0.83 % |
| 17 | hareruyamtg.com        |   292 |     0.48 % |
| 18 | pennydreadfulmagic.com |   249 |     0.41 % |
| 19 | scryfall.com           |   199 |     0.33 % |
| 20 | flexslot.gg            |   199 |     0.33 % |
| 21 | mtgazone.com           |   194 |     0.32 % |
| 22 | magic-ville.com        |   187 |     0.31 % |
| 23 | topdecked.com          |   131 |     0.21 % |
| 24 | old.starcitygames.com  |   117 |     0.19 % |
| 25 | manabox.app            |   105 |     0.17 % |
| 26 | manatraders.com        |    55 |     0.09 % |
| 27 | tcdecks.net            |    54 |     0.09 % |
| 28 | manastack.com          |    38 |     0.06 % |
| 29 | deckbox.org            |    27 |     0.04 % |
| 30 | mtgarena.pro           |    23 |     0.04 % |
| 31 | paupermtg.com          |    22 |     0.04 % |
| 32 | cardhoarder.com        |    20 |     0.03 % |
| 33 | app.cardboard.live     |    14 |     0.02 % |
| 34 | mtgotraders.com        |     1 |     0.00 % |
|  | TOTAL                  | 60967 | 100.00 %|
