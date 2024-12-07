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
    * Links to decklist services are scraped into Deck objects. 31 services are supported so far:
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
        * Deckstats users
        * Flexslot users
        * Goldfish tournaments and players
        * Hareruya events and players
        * MagicVille events and users
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
* I compiled a list of **almost 1.5k** YT channels that feature decks in their descriptions and successfully 
  scraped them (at least 25 videos deep) so this data only waits to be creatively used now!

### How it looks in a Google Sheet
![Most popular channels](assets/channels.jpg)

### Scraped decks breakdown
| No | Format | Count | Percentage |
|:---|:-----|------:|-----------:|
| 1  | commander       | 13924 |    30.85 % |
| 2  | standard        | 11693 |    25.91 % |
| 3  | modern          |  3410 |     7.55 % |
| 4  | pioneer         |  2944 |     6.52 % |
| 5  | pauper          |  1949 |     4.32 % |
| 6  | legacy          |  1923 |     4.26 % |
| 7  | historic        |  1328 |     2.94 % |
| 8  | brawl           |  1250 |     2.77 % |
| 9  | explorer        |  1131 |     2.51 % |
| 10 | undefined       |  1087 |     2.41 % |
| 11 | timeless        |  1048 |     2.32 % |
| 12 | duel            |   990 |     2.19 % |
| 13 | premodern       |   457 |     1.01 % |
| 14 | paupercommander |   387 |     0.86 % |
| 15 | vintage         |   368 |     0.82 % |
| 16 | irregular       |   351 |     0.78 % |
| 17 | alchemy         |   323 |     0.72 % |
| 18 | penny           |   278 |     0.62 % |
| 19 | standardbrawl   |   158 |     0.35 % |
| 20 | oathbreaker     |    69 |     0.15 % |
| 21 | gladiator       |    39 |     0.09 % |
| 22 | oldschool       |    16 |     0.04 % |
| 23 | future          |    14 |     0.03 % |
|  | TOTAL           | 45137 | 100.00 %|

| No | Source | Count | Percentage |
|:---|:-----|------:|-----------:|
| 1  | moxfield.com           | 17438 |    38.63 % |
| 2  | arena.decklist         |  5928 |    13.13 % |
| 3  | aetherhub.com          |  5630 |    12.47 % |
| 4  | mtggoldfish.com        |  5181 |    11.48 % |
| 5  | archidekt.com          |  1848 |     4.09 % |
| 6  | tappedout.net          |  1274 |     2.82 % |
| 7  | mtga.untapped.gg       |  1138 |     2.52 % |
| 8  | melee.gg               |   978 |     2.17 % |
| 9  | mtgtop8.com            |   956 |     2.12 % |
| 10 | streamdecker.com       |   914 |     2.02 % |
| 11 | tcgplayer.com          |   839 |     1.86 % |
| 12 | mtgdecks.net           |   825 |     1.83 % |
| 13 | deckstats.net          |   499 |     1.11 % |
| 14 | pennydreadfulmagic.com |   249 |     0.55 % |
| 15 | hareruyamtg.com        |   234 |     0.52 % |
| 16 | scryfall.com           |   187 |     0.41 % |
| 17 | mtgazone.com           |   186 |     0.41 % |
| 18 | magic-ville.com        |   176 |     0.39 % |
| 19 | flexslot.gg            |   160 |     0.35 % |
| 20 | topdecked.com          |   111 |     0.25 % |
| 21 | manabox.app            |    97 |     0.21 % |
| 22 | tcdecks.net            |    54 |     0.12 % |
| 23 | manatraders.com        |    51 |     0.11 % |
| 24 | mtg.cardsrealm.com     |    43 |     0.10 % |
| 25 | manastack.com          |    38 |     0.08 % |
| 26 | deckbox.org            |    27 |     0.06 % |
| 27 | mtgarena.pro           |    23 |     0.05 % |
| 28 | paupermtg.com          |    21 |     0.05 % |
| 29 | cardhoarder.com        |    20 |     0.04 % |
| 30 | app.cardboard.live     |     9 |     0.02 % |
| 31 | old.starcitygames.com  |     2 |     0.00 % |
| 32 | mtgotraders.com        |     1 |     0.00 % |
|  | TOTAL                  | 45137 | 100.00 %|
