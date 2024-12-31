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
* I compiled a list of **over 1.6k** YT channels that feature decks in their descriptions and successfully 
  scraped them (at least 25 videos deep) so this data only waits to be creatively used now!

### How it looks in a Google Sheet
![Most popular channels](assets/channels.jpg)

### Scraped decks breakdown
| No | Format | Count | Percentage |
|:---|:-----|------:|-----------:|
| 1  | commander       | 17237 |    31.37 % |
| 2  | standard        | 13805 |    25.13 % |
| 3  | modern          |  4299 |     7.82 % |
| 4  | pioneer         |  3389 |     6.17 % |
| 5  | pauper          |  2818 |     5.13 % |
| 6  | legacy          |  2542 |     4.63 % |
| 7  | historic        |  1494 |     2.72 % |
| 8  | brawl           |  1491 |     2.71 % |
| 9  | explorer        |  1376 |     2.50 % |
| 10 | undefined       |  1203 |     2.19 % |
| 11 | timeless        |  1182 |     2.15 % |
| 12 | duel            |  1094 |     1.99 % |
| 13 | premodern       |   584 |     1.06 % |
| 14 | vintage         |   547 |     1.00 % |
| 15 | paupercommander |   467 |     0.85 % |
| 16 | irregular       |   443 |     0.81 % |
| 17 | alchemy         |   364 |     0.66 % |
| 18 | penny           |   278 |     0.51 % |
| 19 | standardbrawl   |   184 |     0.33 % |
| 20 | oathbreaker     |    70 |     0.13 % |
| 21 | gladiator       |    44 |     0.08 % |
| 22 | oldschool       |    19 |     0.03 % |
| 23 | future          |    15 |     0.03 % |
|  | TOTAL           | 54945 | 100.00 %|

| No | Source | Count | Percentage |
|:---|:-----|------:|-----------:|
| 1  | moxfield.com           | 21609 |    39.33 % |
| 2  | arena.decklist         |  7089 |    12.90 % |
| 3  | aetherhub.com          |  6529 |    11.88 % |
| 4  | mtggoldfish.com        |  5816 |    10.59 % |
| 5  | archidekt.com          |  2994 |     5.45 % |
| 6  | mtga.untapped.gg       |  1422 |     2.59 % |
| 7  | tappedout.net          |  1318 |     2.40 % |
| 8  | melee.gg               |  1093 |     1.99 % |
| 9  | streamdecker.com       |  1058 |     1.93 % |
| 10 | mtgtop8.com            |  1038 |     1.89 % |
| 11 | mtgdecks.net           |   973 |     1.77 % |
| 12 | tcgplayer.com          |   923 |     1.68 % |
| 13 | mtg.cardsrealm.com     |   684 |     1.24 % |
| 14 | deckstats.net          |   508 |     0.92 % |
| 15 | hareruyamtg.com        |   274 |     0.50 % |
| 16 | pennydreadfulmagic.com |   249 |     0.45 % |
| 17 | scryfall.com           |   199 |     0.36 % |
| 18 | mtgazone.com           |   193 |     0.35 % |
| 19 | magic-ville.com        |   186 |     0.34 % |
| 20 | flexslot.gg            |   185 |     0.34 % |
| 21 | topdecked.com          |   131 |     0.24 % |
| 22 | old.starcitygames.com  |   116 |     0.21 % |
| 23 | manabox.app            |   105 |     0.19 % |
| 24 | manatraders.com        |    55 |     0.10 % |
| 25 | tcdecks.net            |    54 |     0.10 % |
| 26 | manastack.com          |    38 |     0.07 % |
| 27 | deckbox.org            |    27 |     0.05 % |
| 28 | mtgarena.pro           |    23 |     0.04 % |
| 29 | paupermtg.com          |    22 |     0.04 % |
| 30 | cardhoarder.com        |    20 |     0.04 % |
| 31 | app.cardboard.live     |    13 |     0.02 % |
| 32 | mtgotraders.com        |     1 |     0.00 % |
|  | TOTAL                  | 54945 | 100.00 %|
