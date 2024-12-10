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
| 1  | commander       | 14052 |    30.76 % |
| 2  | standard        | 11877 |    26.00 % |
| 3  | modern          |  3429 |     7.51 % |
| 4  | pioneer         |  2954 |     6.47 % |
| 5  | pauper          |  1956 |     4.28 % |
| 6  | legacy          |  1943 |     4.25 % |
| 7  | historic        |  1360 |     2.98 % |
| 8  | brawl           |  1269 |     2.78 % |
| 9  | explorer        |  1152 |     2.52 % |
| 10 | undefined       |  1101 |     2.41 % |
| 11 | timeless        |  1077 |     2.36 % |
| 12 | duel            |   994 |     2.18 % |
| 13 | premodern       |   464 |     1.02 % |
| 14 | paupercommander |   417 |     0.91 % |
| 15 | vintage         |   369 |     0.81 % |
| 16 | irregular       |   358 |     0.78 % |
| 17 | alchemy         |   330 |     0.72 % |
| 18 | penny           |   278 |     0.61 % |
| 19 | standardbrawl   |   165 |     0.36 % |
| 20 | oathbreaker     |    69 |     0.15 % |
| 21 | gladiator       |    39 |     0.09 % |
| 22 | oldschool       |    16 |     0.04 % |
| 23 | future          |    14 |     0.03 % |
|  | TOTAL           | 45683 | 100.00 %|

| No | Source | Count | Percentage |
|:---|:-----|------:|-----------:|
| 1  | moxfield.com           | 17627 |    38.59 % |
| 2  | arena.decklist         |  6051 |    13.25 % |
| 3  | aetherhub.com          |  5702 |    12.48 % |
| 4  | mtggoldfish.com        |  5218 |    11.42 % |
| 5  | archidekt.com          |  1904 |     4.17 % |
| 6  | tappedout.net          |  1276 |     2.79 % |
| 7  | mtga.untapped.gg       |  1173 |     2.57 % |
| 8  | melee.gg               |   978 |     2.14 % |
| 9  | mtgtop8.com            |   943 |     2.06 % |
| 10 | streamdecker.com       |   916 |     2.01 % |
| 11 | tcgplayer.com          |   853 |     1.87 % |
| 12 | mtgdecks.net           |   837 |     1.83 % |
| 13 | deckstats.net          |   500 |     1.09 % |
| 14 | pennydreadfulmagic.com |   249 |     0.55 % |
| 15 | hareruyamtg.com        |   242 |     0.53 % |
| 16 | scryfall.com           |   187 |     0.41 % |
| 17 | mtgazone.com           |   186 |     0.41 % |
| 18 | magic-ville.com        |   176 |     0.39 % |
| 19 | flexslot.gg            |   163 |     0.36 % |
| 20 | topdecked.com          |   113 |     0.25 % |
| 21 | manabox.app            |   100 |     0.22 % |
| 22 | tcdecks.net            |    54 |     0.12 % |
| 23 | manatraders.com        |    51 |     0.11 % |
| 24 | mtg.cardsrealm.com     |    43 |     0.09 % |
| 25 | manastack.com          |    38 |     0.08 % |
| 26 | deckbox.org            |    27 |     0.06 % |
| 27 | mtgarena.pro           |    23 |     0.05 % |
| 28 | paupermtg.com          |    21 |     0.05 % |
| 29 | cardhoarder.com        |    20 |     0.04 % |
| 30 | app.cardboard.live     |     9 |     0.02 % |
| 31 | old.starcitygames.com  |     2 |     0.00 % |
| 32 | mtgotraders.com        |     1 |     0.00 % |
|  | TOTAL                  | 45683 | 100.00 %|
