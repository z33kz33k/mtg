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
    * Links to decklist services are scraped into Deck objects. 32 services are supported so far:
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
    * Both old and new TCGPlayer sites are supported
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
        * LigaMagic events
        * MagicVille events and users
        * Manatraders users
        * Melee.gg tournaments
        * Moxfield bookmarks and users
        * MTGDecks.net tournaments
        * MTGTop8 events
        * PennyDreadfulMagic competitions and users
        * Streamdecker users
        * TappedOut users, folders, and user folders
        * TCDecks events
        * TCGPlayer (old-site) players
        * TCGPlayer (new-site) players (profile page), authors (search page) and events
        * Untapped profiles
        * others in plans
* Assessing the meta:
    * Scraping Goldfish and MGTAZone for meta-decks (others in plans)
    * Scraping a singular Untapped meta-deck decklist page
* Exporting decks into a [Forge MTG](https://github.com/Card-Forge/forge) .dck format or Arena 
  decklist saved into a .txt file - with autogenerated, descriptive names based on scraped deck's 
  metadata
* Importing back into a Deck from those formats
* Export/import to other formats in plans
* Dumping decks, YT videos and channels to .json
* I compiled a list of **almost 1.6k** YT channels that feature decks in their descriptions and successfully 
  scraped them (at least 25 videos deep) so this data only waits to be creatively used now!

### How it looks in a Google Sheet
![Most popular channels](assets/channels.jpg)

### Scraped decks breakdown
| No | Format | Count | Percentage |
|:---|:-----|------:|-----------:|
| 1  | commander       | 15985 |    30.63 % |
| 2  | standard        | 13541 |    25.94 % |
| 3  | modern          |  4003 |     7.67 % |
| 4  | pioneer         |  3320 |     6.36 % |
| 5  | pauper          |  2691 |     5.16 % |
| 6  | legacy          |  2198 |     4.21 % |
| 7  | historic        |  1463 |     2.80 % |
| 8  | brawl           |  1452 |     2.78 % |
| 9  | explorer        |  1343 |     2.57 % |
| 10 | undefined       |  1190 |     2.28 % |
| 11 | timeless        |  1174 |     2.25 % |
| 12 | duel            |  1042 |     2.00 % |
| 13 | premodern       |   557 |     1.07 % |
| 14 | paupercommander |   460 |     0.88 % |
| 15 | vintage         |   415 |     0.80 % |
| 16 | irregular       |   393 |     0.75 % |
| 17 | alchemy         |   360 |     0.69 % |
| 18 | penny           |   278 |     0.53 % |
| 19 | standardbrawl   |   184 |     0.35 % |
| 20 | oathbreaker     |    69 |     0.13 % |
| 21 | gladiator       |    44 |     0.08 % |
| 22 | oldschool       |    17 |     0.03 % |
| 23 | future          |    14 |     0.03 % |
|  | TOTAL           | 52193 | 100.00 %|

| No | Source | Count | Percentage |
|:---|:-----|------:|-----------:|
| 1  | moxfield.com           | 19845 |    38.02 % |
| 2  | arena.decklist         |  6956 |    13.33 % |
| 3  | aetherhub.com          |  6450 |    12.36 % |
| 4  | mtggoldfish.com        |  5707 |    10.93 % |
| 5  | archidekt.com          |  2667 |     5.11 % |
| 6  | mtga.untapped.gg       |  1387 |     2.66 % |
| 7  | tappedout.net          |  1287 |     2.47 % |
| 8  | streamdecker.com       |  1054 |     2.02 % |
| 9  | melee.gg               |  1048 |     2.01 % |
| 10 | mtgtop8.com            |  1015 |     1.94 % |
| 11 | mtgdecks.net           |   971 |     1.86 % |
| 12 | tcgplayer.com          |   899 |     1.72 % |
| 13 | mtg.cardsrealm.com     |   636 |     1.22 % |
| 14 | deckstats.net          |   506 |     0.97 % |
| 15 | hareruyamtg.com        |   272 |     0.52 % |
| 16 | pennydreadfulmagic.com |   249 |     0.48 % |
| 17 | scryfall.com           |   198 |     0.38 % |
| 18 | mtgazone.com           |   191 |     0.37 % |
| 19 | magic-ville.com        |   186 |     0.36 % |
| 20 | flexslot.gg            |   182 |     0.35 % |
| 21 | topdecked.com          |   129 |     0.25 % |
| 22 | manabox.app            |   104 |     0.20 % |
| 23 | manatraders.com        |    55 |     0.11 % |
| 24 | tcdecks.net            |    54 |     0.10 % |
| 25 | manastack.com          |    38 |     0.07 % |
| 26 | deckbox.org            |    27 |     0.05 % |
| 27 | mtgarena.pro           |    23 |     0.04 % |
| 28 | paupermtg.com          |    22 |     0.04 % |
| 29 | cardhoarder.com        |    20 |     0.04 % |
| 30 | app.cardboard.live     |    12 |     0.02 % |
| 31 | old.starcitygames.com  |     2 |     0.00 % |
| 32 | mtgotraders.com        |     1 |     0.00 % |
|  | TOTAL                  | 52193 | 100.00 %|
