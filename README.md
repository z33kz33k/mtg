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
    * Links to decklist services are scraped into Deck objects. 27 services are supported so far:
        * [Aetherhub](https://aetherhub.com)
        * [Archidekt](https://archidekt.com)
        * [CardBoard Live](https://cardboard.live)
        * [Cardhoarder](https://www.cardhoarder.com)
        * [Cardsrealm](https://mtg.cardsrealm.com/en-us/)
        * [Deckbox](https://deckbox.org)
        * [Deckstats.net](https://deckstats.net)
        * [Flexslot](https://flexslot.gg)
        * [Goldfish](https://www.mtggoldfish.com)
        * [Hareruya](https://www.hareruyamtg.com/en/)
        * [Manatraders](https://www.manatraders.com)
        * [ManaStack](https://manastack.com/home)
        * [Melee.gg](https://melee.gg)
        * [Moxfield](https://www.moxfield.com)
        * [MTGArena.Pro](https://mtgarena.pro)
        * [MTGAZone](https://mtgazone.com)
        * [MTGDecks.net](https://mtgdecks.net)
        * [MTGO Traders](https://www.mtgotraders.com/store/index.html)
        * [MTGTop8](https://mtgtop8.com/index)
        * [PennyDreadfulMagic](https://pennydreadfulmagic.com)
        * [Scryfall](https://scryfall.com)
        * [StarCityGames](https://starcitygames.com)
        * [Streamdecker](https://www.streamdecker.com/landing)
        * [TappedOut](https://tappedout.net)
        * [TCGPlayer](https://infinite.tcgplayer.com)
        * [TopDecked](https://www.topdecked.com)
        * [Untapped](https://mtga.untapped.gg) 
    * Other decklist services are in plans (but, it does seem like I've pretty much exhausted the 
      possibilities already :))
    * Both Untapped decklist types featured in YT videos are supported: regular deck and profile deck
    * Both old and new TCGPlayer sites are supported
    * Both international and Japanese Hareruya sites are supported 
    * Sites that need it are scraped using [Selenium](https://github.com/SeleniumHQ/Selenium)
    * All those mentioned above work even if they are behind shortener links and need unshortening first
    * Text decklists in links to pastebin-like services (like [Amazonian](https://www.youtube.com/@Amazonian) does) work too
    * If nothing is found in the video's description, then the author's comments are parsed
    * Deck's name and format are derived if not readily available
    * Foreign cards and other that cannot be found in the downloaded Scryfall bulk data are looked 
      up with queries to the Scryfall API
    * Individual decklist URLs are extracted from container pages and further processed for decks. 
      These include:
        * Moxfield bookmarks and users
        * MTGTop8 events
        * Archidekt folders and users
        * Hareruya events
        * Aetherhub users
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
* I compiled a list of **over 1.2k** YT channels that feature decks in their descriptions and successfully 
  scraped them (at least 25 videos deep) so this data only waits to be creatively used now!

### How it looks in a Google Sheet
![Most popular channels](assets/channels.jpg)

### Scraped decks breakdown
| No | Format | Count | Percentage |
|:---|:-----|------:|-----------:|
| 1  | standard        | 7617 |    29.48 % |
| 2  | commander       | 7455 |    28.85 % |
| 3  | modern          | 2284 |     8.84 % |
| 4  | legacy          |  993 |     3.84 % |
| 5  | historic        |  951 |     3.68 % |
| 6  | brawl           |  864 |     3.34 % |
| 7  | pioneer         |  854 |     3.31 % |
| 8  | timeless        |  823 |     3.19 % |
| 9  | explorer        |  816 |     3.16 % |
| 10 | undefined       |  706 |     2.73 % |
| 11 | pauper          |  693 |     2.68 % |
| 12 | duel            |  628 |     2.43 % |
| 13 | alchemy         |  249 |     0.96 % |
| 14 | premodern       |  247 |     0.96 % |
| 15 | paupercommander |  216 |     0.84 % |
| 16 | standardbrawl   |  110 |     0.43 % |
| 17 | penny           |  102 |     0.39 % |
| 18 | irregular       |   86 |     0.33 % |
| 19 | vintage         |   73 |     0.28 % |
| 20 | oathbreaker     |   33 |     0.13 % |
| 21 | gladiator       |   17 |     0.07 % |
| 22 | oldschool       |   14 |     0.05 % |
| 23 | future          |    7 |     0.03 % |
|  | TOTAL           | 25838 | 100.00 %|

| No | Source | Count | Percentage |
|:---|:-----|------:|-----------:|
| 1  | moxfield.com           | 9307 |    36.02 % |
| 2  | aetherhub.com          | 4351 |    16.84 % |
| 3  | arena.decklist         | 3909 |    15.13 % |
| 4  | mtggoldfish.com        | 2221 |     8.60 % |
| 5  | archidekt.com          | 1170 |     4.53 % |
| 6  | mtgtop8.com            |  776 |     3.00 % |
| 7  | mtga.untapped.gg       |  694 |     2.69 % |
| 8  | streamdecker.com       |  646 |     2.50 % |
| 9  | tcgplayer.com          |  546 |     2.11 % |
| 10 | tappedout.net          |  502 |     1.94 % |
| 11 | melee.gg               |  295 |     1.14 % |
| 12 | mtgdecks.net           |  235 |     0.91 % |
| 13 | deckstats.net          |  233 |     0.90 % |
| 14 | scryfall.com           |  166 |     0.64 % |
| 15 | mtgazone.com           |  165 |     0.64 % |
| 16 | hareruyamtg.com        |  164 |     0.63 % |
| 17 | flexslot.gg            |  107 |     0.41 % |
| 18 | pennydreadfulmagic.com |   73 |     0.28 % |
| 19 | topdecked.com          |   69 |     0.27 % |
| 20 | manatraders.com        |   51 |     0.20 % |
| 21 | mtg.cardsrealm.com     |   40 |     0.15 % |
| 22 | manastack.com          |   38 |     0.15 % |
| 23 | deckbox.org            |   25 |     0.10 % |
| 24 | mtgarena.pro           |   23 |     0.09 % |
| 25 | cardhoarder.com        |   20 |     0.08 % |
| 26 | app.cardboard.live     |    9 |     0.03 % |
| 27 | old.starcitygames.com  |    2 |     0.01 % |
| 28 | mtgotraders.com        |    1 |     0.00 % |
|  | TOTAL                  | 25838 | 100.00 %|
