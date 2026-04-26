"""

    mtg.yt.rescrape
    ~~~~~~~~~~~~~~~
    Re-scrape designated videos.

    @author: mazz3rr

"""
import logging
from collections.abc import Callable
from datetime import date

from mtg.data.common import retrieve_ids, retrieve_video_data
from mtg.data.structs import VideoData
from mtg.session import ScrapingSession
from mtg.lib.time import timed
from mtg.lib.scrape.core import http_requests_counted
from mtg.yt.scrape import scrape_channel_videos

_log = logging.getLogger(__name__)


@http_requests_counted("re-scraping videos")
@timed("re-scraping videos")
def rescrape_videos(
        *chids: str, video_filter: Callable[[VideoData], bool] = lambda _: True) -> None:
    """Re-scrape videos across all specified channels. Optionally, define a video-filtering
    predicate.

    The default for scraping is all known channels and all their videos.

    Args:
        *chids: channel YouTube IDs
        video_filter: video-filtering predicate
    """
    chids = chids or retrieve_ids()
    channels = retrieve_video_data(*chids, video_filter=video_filter)

    if not channels:
        _log.info("No videos found that needed re-scraping")
        return

    with ScrapingSession(ignore_scraped=True, ignore_failed=True) as session:
        session.remove_videos(set(v.yt_id for lst in channels.values() for v in lst))
        for i, (channel_id, videos) in enumerate(channels.items(), start=1):
            _log.info(
                f"Re-scraping {len(videos)} video(s) of ==> {i}/{len(channels)} <== channel...")
            scrape_channel_videos(session, channel_id, *(v.yt_id for v in videos))


def rescrape_by_date(
        *chids: str, after: date | None = None, before: date | None = None,
        video_filter: Callable[[VideoData], bool] = lambda _: True) -> None:
    """Re-scrape videos across all specified channels but only those scraped before/after the
    specified threshold dates (or inbetween them).

    If not specified, all known channels are considered.

    Args:
        *chids: channel IDs
        after: scrape videos after or equal to this date (if specified)
        before: scrape videos before this date (if specified)
        video_filter: optionally, additional video-filtering predicate
    """
    if after and before:
        rescrape_videos(
            *chids,
            video_filter=lambda v: v.scrape_time
                                   and before > v.scrape_time.date() >= after
                                   and video_filter(v)
        )
    elif after:
        rescrape_videos(
            *chids,
            video_filter=lambda v: v.scrape_time
                                   and v.scrape_time.date() >= after
                                   and video_filter(v)
        )
    elif before:
        rescrape_videos(
            *chids,
            video_filter=lambda v: v.scrape_time
                                   and before > v.scrape_time.date()
                                   and video_filter(v)
        )
    else:
        raise ValueError("At least one threshold date must be specified")


def rescrape_by_urls_pool(urls_pool: set[str], *chids: str, exact=False) -> None:
    """Re-scrape videos across all specified channels but only those that feature URLs present in
    ``urls_pool``.

    If not specified, all known channels are considered.

    Args:
        urls_pool: set of URLs to filter against
        *chids: channel IDs
        exact: if True only exact match counts, else partial match is enough
    """
    def check_partial(video: VideoData) -> bool:
        for featured_url in video.featured_urls:
            for pool_url in urls_pool:
                if pool_url in featured_url:
                    return True
        return False

    if exact:
        rescrape_videos(
            *chids,
            video_filter=lambda v: any(l in urls_pool for l in v.featured_urls)
        )
    rescrape_videos(
        *chids,
        video_filter=lambda v: check_partial(v)
    )


def rescrape_by_url_predicate(url_predicate: Callable[[str], bool], *chids: str) -> None:
    """Re-scrape videos across all specified channels but only those that feature URLs satisfying
    the provided predicate.

    If not specified, all known channels are considered.

    Args:
        url_predicate: URL-filtering predicate
        *chids: channel IDs
    """
    rescrape_videos(
        *chids,
        video_filter=lambda v: any(url_predicate(l) for l in v.featured_urls)
    )
