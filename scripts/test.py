"""

    scripts.test
    ~~~~~~~~~~~~
    Script to test validity of the scraping logic against live websites using known valid URLs.

    @author: mazz3rr

"""
import logging
import sys

from mtg.lib.time import timed
from mtg.logging import init_log
from mtg.deck.scrapers.abc import (
    DeckScraper, DeckUrlsContainerScraper, DecksJsonContainerScraper, DeckTagsContainerScraper,
    HybridContainerScraper)


_log = logging.getLogger(__name__)

# TODO: make this work async (group URLs into batches and run concurrently)


# TODO: finish curating the URLs
TEST_URLS = [
    'https://aetherhub.com/Deck/tmnt-boros-ascension',
    'https://aetherhub.com/Decks/Writeups/Traditional-Standard/shenanigans-two-day-dec-21-22-std-rcq',
    'https://aetherhub.com/User/LegenVD',
    'https://aetherhub.com/User/LegenVD/Decks/Standard-BO1',
    'https://aetherhub.com/Events/Standard/10838',
    'https://aetherhub.com/Article/Theros-Beyond-Death-Fresh-new-decks',
    'https://aetherhub.com/Article/An-Aetherhub-Power-Panel-Breaks-Down-Mythic-Championship-V',
    'https://aetherhub.com/Article/First-Tournament-decklists-post-Oko-ban',
    'https://archidekt.com/decks/16069812/zombie_horde',
    'https://archidekt.com/snapshots/47613',
    'https://archidekt.com/folders/42773?orderBy=name&dir=asc',
    'https://archidekt.com/u/tauna',
    'https://archidekt.com/user/5879',
    'https://archidekt.com/search/decks?owner=BacaIhau&ownerexact=true',
    'https://app.cardboard.live/shared-deck/e75ebecd-6bec-11ec-8b34-12f15ef2af51?channel_id=38054155',
    'https://www.cardhoarder.com/d/kpy674jn6ekerj5',
    'https://blog.cardkingdom.com/river-song-commander-deck-tech/',
    'https://blog.cardkingdom.com/author/kgregory/',
    'https://www.cardmarket.com/en/Insight/Articles/quest-for-the-best-pioneer-deck-ever',
    'https://www.cardmarket.com/en/Insight/Writers/tobi-henke',
    'https://mtg.cardsrealm.com/en-us/decks/io11-bg-harvest?utm_source=monarchs&utm_medium=affiliate&utm_campaign=podcast',
    'https://mtg.cardsrealm.com/en-us/decks/folder/1l7-pauper',
    'https://mtg.cardsrealm.com/en-us/profile/mateus-queiroz-n35/decks',
    'https://mtg.cardsrealm.com/en-us/meta-decks/pauper/tournaments/1k27j-pauper-royale-220',
    'https://mtg.cardsrealm.com/en-us/tournament/1k27j-pauper-royale-220',
    'https://mtg.cardsrealm.com/en-us/articles/explorer-mono-blue-tempo-deck-tech-sideboard-guide',
    'https://cardsrealm.com/en-us/articles/author/humberto2151',
    'https://cardsrealm.com/en-us/articles/search/?keyword=humberto2151',
    'https://www.channelfireball.com/magic-the-gathering/deck/Timeless-Grixis/481595?external=undefined',
    'https://www.channelfireball.com/magic-the-gathering/decks/player/Martin%20Juza',
    'https://www.channelfireball.com/author/Frank-Karsten/7f203152-211a-478d-8fee-464c2aeca2cd',
    'https://www.channelfireball.com/article/MTG-Deck-Guide-Standard-Gruul-Aggro/bd06ac65-bb14-442c-aed5-cb9195861496/',
    'https://commandersherald.com/araumi-of-the-dead-tide-pauper-commander/',
    'https://commandersherald.com/dueling-deck-techs-equipment/',
    'https://commandersherald.com/author/cody-collins/',
    'https://www.coolstuffinc.com/a/matthewlotti-02142025-skeletal-swindling-with-tinybones-bauble-burglar-in-commander',
    'https://www.coolstuffinc.com/a/jimdavis-05152023-a-new-two-card-infinite-combo-in-standard',
    'https://www.coolstuffinc.com/a/?action=search&page=1&author%5B%5D=Carlos%20Gutierrez',
    'https://cyclesgaming.com/ephara-god-of-the-polis-u-w-flash/',
    'https://cyclesgaming.com/keeping-modern-janky-duskmourn-glimmers/',
    'https://deckbox.org/sets/3581335',
    'https://deckbox.org/users/Odekar',
    'https://deckbox.org/communities/mtg_competitive_events/events/1989',
    'https://deckstats.net/decks/231485/4286921-captain-n-ghathrod',
    'https://deckstats.net/decks/115134/1283677-kaya-s-scourge',
    'https://deckstats.net/decks/30513',
    'https://deckstats.net/decks/30513/?lng=it',
    'https://deckstats.net/decks/202938/?lng=fr',
    'https://draftsim.com/decks/polymorph/',
    'https://draftsim.com/author/darthjacen/',
    'https://draftsim.com/fynn-edh-deck/',
    'https://draftsim.com/mtg-dft-commander-decks/',
    'https://edhrec.com/deckpreview/mgRcVo95TJj9ztl2dHMBPw',
    'https://edhrec.com/average-decks/honest-rutstein',
    'https://edhrec.com/articles/search/tyler%20bucks',
    'https://edhrec.com/articles/author/angelo-guerrera',
    'https://articles.edhrec.com/author/joseph-schultz',
    'https://edhrec.com/articles/living-energy-precon-review-aetherdrift',
    'https://edhtop16.com/commander/Niv-Mizzet%2C%20Visionary',
    'https://edhtop16.com/tournament/Mh2edH1jY19LaTovso33',
    'https://edhtop16.com/tournament/landfall-3er-clasificatorio-al-nacional-de-cedh',
    'https://flexslot.gg/decks/243fc88f-1fca-41ae-a81a-9503347ce85c',
    'https://flexslot.gg/u/YungDingo',
    'https://flexslot.gg/sideboards/7861',
    'https://flexslot.gg/articles/a3222f36-64f1-43b1-9b5a-94dffa76459a',
    # CURATED ABOVE / UNCURATED BELOW
    'https://www.hareruyamtg.com/en/deck/result?player=pg8',
    'https://article.hareruyamtg.com/article/91861/?lang=en',
    'https://article.hareruyamtg.com/article/author/piotrglogowski_en/?lang=en',
    'https://magic.wizards.com/en/news/archive?author=1iuVapWGRdDkVKUHT2xffq',
    'https://magic.wizards.com/en/news/feature/upgrading-the-miracle-worker-duskmourn-house-of-horror-commander-deck',
    'https://magicblogs.de/blog/9893-in-a-land-before-the-monkey-aggro-5-5-sliver/',
    'https://magicjank.com/magicjank-explorer-best-decks/',
    'https://manastack.com/user/kxdx1157/decks',
    'https://www.manatraders.com/decks?format_id=4&search_name=kasa',
    'https://melee.gg/Profile/Index/MAJH81996',
    'https://moxfield.com/decks/public?q=eyJmaWx0ZXIiOiJwb2cyNTAxIn0%3D',
    'https://mtgazone.com/author/mtghero/',
    'https://mtgcircle.com/articles/standard-banner-goblins',
    'https://mtgcircle.com/creators/numbskull/articles',
    'https://mtgcircle.com/decks/standard/mono-red-aggro-decklist-by-cunicoligoblin?id=679b6f7fbcc7d768c3123f7c',
    'https://mtgdecks.net/authors/skura',
    'https://www.mtggoldfish.com/articles/search?author=93',
    'https://mtgmeta.io/articles/author/vertyx/'
    'https://mtgrocks.com/author/zachary-fink/',
    'https://mtgrocks.com/songcrafter-mage-temur-turns-modern-mtg/',
    'https://www.mtgsalvation.com/articles/features/49796-in-defense-of-the-pre-constructed-magic-deck',
    'https://www.mtgsalvation.com/decks/16487-w-lifegain',
    'https://www.mtgstocks.com/decks/481330',
    'https://www.mtgstocks.com/news/1061-weekly-winners-2021---20',
    'https://www.mtgvault.com/ahendra/',
    'https://www.mtgvault.com/rogib/decks/edh-for-fun-special-garruk/',
    'https://articles.nerdragegaming.com/the-start-of-something-1st-place-at-nrgchamp/',
    'https://www.pauperwave.com/author/crila-peoty/',
    'https://www.pauperwave.com/top-8-master-of-pauper-vol-2',
    'https://pennydreadfulmagic.com/seasons/33/people/id/2999/',
    'https://playingmtg.com/author/dirkbondster/',
    'https://playingmtg.com/pro-tour-aetherdrift-top-8-standard-decklists/',
    'https://playingmtg.com/tournaments/mtgo-league-3164/',
    'https://www.quietspeculation.com/2023/07/faces-of-aggro-boros-pia-aggro-in-pioneer/',
    'https://spikesacademy.com/p/deck-spotlight-ub-mill',
    'https://old.starcitygames.com/content/bennie-smith-decks',
    'https://articles.starcitygames.com/author/john-hall/',
    'https://tappedout.net/mtg-decks/14-11-17-modern-bant',
    'https://tcgrocks.com/mtg/deck-builder/embed/627c8696-51db-4f09-8c28-5f263f8713e1',
    'https://infinite.tcgplayer.com/article/What-is-Dand%C3%A2n-MTG-s-Forgetful-Fish-Format/7d6590b5-8e78-44f5-92c6-511049676fea/',
    'https://infinite.tcgplayer.com/author/Critical-Role',
    'https://infinite.tcgplayer.com/magic-the-gathering/decks/advanced-search?author=SBMTGDev&p=1',
    'https://infinite.tcgplayer.com/magic-the-gathering/decks/player/SBMTGDev',
    'https://infinite.tcgplayer.com/magic-the-gathering/events/event/MTGO%20Standard%20Challenge%2032%20-%2011-12-2024',
    'https://www.thegamer.com/magic-the-gathering-mtg-braids-cabal-minion-commander-deck-guide/',
    'https://thegathering.gg/neat-decking-11-23/',
    'https://thegathering.gg/standard-decks/gruul-aggro/',
    'https://themanabase.com/author/spirit-squad-mtg/',
    'https://topdeck.gg/bracket/D1NrlZYtYPr8HZgygm2G',
    'https://topdeck.gg/deck/jeweled-lotus-lattenkamp-2025/VXJvfKI8RrPtKdYYC2zMBbuAPgu1',
    'https://topdeck.gg/profile/XThcd3jrjqTHleEtnr9FAm3kIIv1',
    'https://ultimateguard.com/en/blog/a-breakdown-of-standard-gruul-vs-dimir-midrange-magic-the-gathering-seth-manfield',
    # UNSUPPORTED
    'https://burnmana.com/en/mtg-decks/standard/mono-red-aggro/fced354d-9a02-4c2b-abc0-f74393f65301',
    'https://app.cardboard.live/s/anzidmtg',
    'https://blog.cardsphere.com/sphere-of-influence-july-11-2025/',
    'https://www.dicebreaker.com/games/magic-the-gathering-game/best-games/best-mtg-arena-decks',
    'https://magic.facetofacegames.com/f2f-tour-halifax-2025-modern-super-qualifier-top-8-decklists/',
    'https://www.fanfinity.gg/blog/5-modern-decks-supercharged-with-final-fantasy/'
    'https://www.hipstersofthecoast.com/2025/03/jundjund-a-dandan-variant-for-midrange-players/',
    'https://krakenthemeta.com/deck-view?deckId=S4s10xy9vDTErG4jJ8kY',
]


@timed("testing scrapers")
def test_scrapers():
    """Test all registered scrapers with their example URLs.
    """
    passed, failed = [], []

    scrapers: list[type[DeckScraper]] = []
    scrapers += DeckScraper.get_registered_scrapers()
    scrapers += DeckUrlsContainerScraper.get_registered_scrapers()
    scrapers += DecksJsonContainerScraper.get_registered_scrapers()
    scrapers += DeckTagsContainerScraper.get_registered_scrapers()
    scrapers += HybridContainerScraper.get_registered_scrapers()

    for i, scraper in enumerate(scrapers, start=1):
        name = scraper.__name__
        _log.info(f"Testing {i}/{len(scrapers)} scraper: {name!r}...")
        result, exc = scraper.test()
        if result:
            _log.info(f"✓ {name!r} scraper: PASSED")
            passed.append(scraper)
        else:
            _log.warning(f"✗ {name!r} scraper: FAILED - {exc}")
            failed.append(scraper)

        _log.info(f"{len(passed)} scrapers passed. {len(failed)} scrapers failed.")


if __name__ == '__main__':
    init_log()
    sys.exit(test_scrapers())
