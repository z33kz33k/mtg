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
    * Links to decklist services are scraped into Deck objects. 29 services are supported so far:
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
        * [Manatraders](https://www.manatraders.com)
        * [ManaStack](https://manastack.com/home)
        * [Melee.gg](https://melee.gg)
        * [Moxfield](https://www.moxfield.com)
        * [MTGArena.Pro](https://mtgarena.pro)
        * [MTGAZone](https://mtgazone.com)
        * [MTGDecks.net](https://mtgdecks.net)
        * [MTGOTraders](https://www.mtgotraders.com/store/index.html)
        * [MTGTop8](https://mtgtop8.com/index)
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
        * Aetherhub users
        * Archidekt folders and users
        * Deckstats users
        * Hareruya events
        * Goldfish tournaments
        * Moxfield bookmarks and users
        * MTGTop8 events
        * Streamdecker users
        * TappedOut users, folders, and user folders
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
* I compiled a list of **over 1.3k** YT channels that feature decks in their descriptions and successfully 
  scraped them (at least 25 videos deep) so this data only waits to be creatively used now!

### How it looks in a Google Sheet
![Most popular channels](assets/channels.jpg)

### Scraped decks breakdown
| No | Format | Count | Percentage |
|:---|:-----|------:|-----------:|
| 1  | commander       | 10192 |    31.54 % |
| 2  | standard        |  8822 |    27.30 % |
| 3  | modern          |  2876 |     8.90 % |
| 4  | legacy          |  1350 |     4.18 % |
| 5  | historic        |  1153 |     3.57 % |
| 6  | brawl           |  1073 |     3.32 % |
| 7  | pioneer         |  1011 |     3.13 % |
| 8  | explorer        |   953 |     2.95 % |
| 9  | timeless        |   904 |     2.80 % |
| 10 | duel            |   848 |     2.62 % |
| 11 | pauper          |   847 |     2.62 % |
| 12 | undefined       |   798 |     2.47 % |
| 13 | premodern       |   290 |     0.90 % |
| 14 | paupercommander |   285 |     0.88 % |
| 15 | alchemy         |   270 |     0.84 % |
| 16 | irregular       |   165 |     0.51 % |
| 17 | vintage         |   143 |     0.44 % |
| 18 | standardbrawl   |   123 |     0.38 % |
| 19 | penny           |   104 |     0.32 % |
| 20 | oathbreaker     |    49 |     0.15 % |
| 21 | gladiator       |    36 |     0.11 % |
| 22 | oldschool       |    16 |     0.05 % |
| 23 | future          |    11 |     0.03 % |
|  | TOTAL           | 32319 | 100.00 %|

| No | Source | Count | Percentage |
|:---|:-----|------:|-----------:|
| 1  | moxfield.com           | 12965 |    40.12 % |
| 2  | aetherhub.com          |  4893 |    15.14 % |
| 3  | arena.decklist         |  4601 |    14.24 % |
| 4  | mtggoldfish.com        |  2387 |     7.39 % |
| 5  | archidekt.com          |  1610 |     4.98 % |
| 6  | streamdecker.com       |   833 |     2.58 % |
| 7  | mtgtop8.com            |   828 |     2.56 % |
| 8  | mtga.untapped.gg       |   798 |     2.47 % |
| 9  | tappedout.net          |   627 |     1.94 % |
| 10 | tcgplayer.com          |   567 |     1.75 % |
| 11 | deckstats.net          |   476 |     1.47 % |
| 12 | melee.gg               |   296 |     0.92 % |
| 13 | mtgdecks.net           |   257 |     0.80 % |
| 14 | hareruyamtg.com        |   179 |     0.55 % |
| 15 | scryfall.com           |   177 |     0.55 % |
| 16 | mtgazone.com           |   170 |     0.53 % |
| 17 | magic-ville.com        |   161 |     0.50 % |
| 18 | flexslot.gg            |   125 |     0.39 % |
| 19 | topdecked.com          |    84 |     0.26 % |
| 20 | pennydreadfulmagic.com |    75 |     0.23 % |
| 21 | manatraders.com        |    51 |     0.16 % |
| 22 | mtg.cardsrealm.com     |    41 |     0.13 % |
| 23 | manastack.com          |    38 |     0.12 % |
| 24 | deckbox.org            |    25 |     0.08 % |
| 25 | mtgarena.pro           |    23 |     0.07 % |
| 26 | cardhoarder.com        |    20 |     0.06 % |
| 27 | app.cardboard.live     |     9 |     0.03 % |
| 28 | old.starcitygames.com  |     2 |     0.01 % |
| 29 | mtgotraders.com        |     1 |     0.00 % |
|  | TOTAL                  | 32319 | 100.00 %|
