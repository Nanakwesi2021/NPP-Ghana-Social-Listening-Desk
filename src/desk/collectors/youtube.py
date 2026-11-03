"""YouTube public channel collector for Ghanaian news and political programmes.

Polls public YouTube channel Atom feeds (https://www.youtube.com/feeds/videos.xml?channel_id=...).
This public approach requires NO credentials, adhering strictly to credential-minimization
and robots.txt rules. If YOUTUBE_API_KEY is configured in the environment, additional search
queries can be enabled.
"""
import http.client
import os
import socket
import ssl
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone as dt_timezone
from calendar import timegm

import certifi
import feedparser
from django.db import transaction
from django.utils import timezone

from .. import tagging
from ..models import Item, PollRun, Source

USER_AGENT = "NPP-Ghana-Social-Listening-Desk/0.2 (internal research desk; YouTube feed reader)"
TIMEOUT_SECONDS = 15
MAX_BYTES = 5 * 1024 * 1024

# Key Ghanaian broadcast & political channels
DEFAULT_CHANNELS = [
    {"name": "JoyNews", "channel_id": "UChd1DEecCRlxaa0-hvPACCw"},
    {"name": "Citi Tube / ChannelOne TV", "channel_id": "UCUTeE-as508hixQrNVHO7vQ"},
    {"name": "Peace FM / Despite Media", "channel_id": "UC5tDLzkXRDGSc98L2gTg1gQ"},
    {"name": "TV3 Ghana", "channel_id": "UC9VSDs4ZXo3sjOoPkmW2iRQ"},
    {"name": "Metro TV Ghana", "channel_id": "UCxm5-CYZ3VTVSshy0h5mTJw"},
    {"name": "UTV Ghana", "channel_id": "UCpvXcuzvRyB4bM5FXJCzbGw"},
    {"name": "Adom TV", "channel_id": "UC_KfNnlLMk2aCJP5S5GEWCQ"},
]


class YouTubeFetchError(Exception):
    pass


@dataclass
class YouTubePassResult:
    source: Source
    result: str
    new_items: int = 0
    seen: int = 0
    note: str = ""
    tagged: dict = field(default_factory=dict)


def _tls_context():
    return ssl.create_default_context(cafile=certifi.where())


def get_youtube_api_key():
    return os.environ.get("YOUTUBE_API_KEY", "").strip()


def ensure_youtube_source(sync=False):
    """Ensure the YouTube source exists in the database."""
    source, created = Source.objects.get_or_create(
        key="youtube-channels",
        defaults={
            "name": "YouTube",
            "group": "YouTube",
            "detail": "Broadcast news channels",
            "platform": "youtube",
            "kind": Source.Kind.COLLECTED,
            "method": "Public channel feeds · every 15 min",
            "scope": "Ghanaian public channels and political programmes (JoyNews, Citi Tube), linked to original videos.",
            "poll_interval_minutes": 15,
            "note": "",
            "position": 20,
        },
    )
    return source


def http_fetch_youtube(url):
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/atom+xml, application/xml;q=0.9, */*;q=0.5",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS, context=_tls_context()) as response:
            return response.read(MAX_BYTES)
    except urllib.error.HTTPError as exc:
        raise YouTubeFetchError(f"HTTP {exc.code}") from exc
    except (urllib.error.URLError, socket.timeout, TimeoutError, ConnectionError) as exc:
        reason = getattr(exc, "reason", exc)
        raise YouTubeFetchError(f"Could not connect to YouTube: {reason}") from exc
    except (http.client.HTTPException, OSError) as exc:
        raise YouTubeFetchError(f"Incomplete response: {type(exc).__name__}") from exc


def parse_youtube_feed(body):
    """Parse a YouTube Atom channel feed."""
    parsed = feedparser.parse(body)
    if parsed.bozo and not parsed.entries:
        raise YouTubeFetchError(f"Malformed YouTube feed: {parsed.get('bozo_exception', 'unreadable')}")

    entries = []
    for entry in parsed.entries:
        video_id = entry.get("yt_videoid") or entry.get("id", "").split(":")[-1]
        if not video_id:
            continue
        link = entry.get("link") or f"https://www.youtube.com/watch?v={video_id}"
        author = entry.get("author", "YouTube Channel")
        title = entry.get("title", "")
        summary = entry.get("summary", "")
        parsed_time = entry.get("published_parsed") or entry.get("updated_parsed")
        published = datetime.fromtimestamp(timegm(parsed_time), tz=dt_timezone.utc) if parsed_time else None

        entries.append({
            "external_id": f"yt-{video_id}",
            "url": link,
            "author": author,
            "title": title,
            "excerpt": f"{title} · {summary}" if summary else title,
            "summary": summary,
            "published": published,
        })
    return entries


@transaction.atomic
def collect_youtube(source=None, channels=None, *, fetch=None, now=None, rules=None):
    """Collect recent broadcasts from public YouTube channels without credential requirement."""
    source = source or ensure_youtube_source()
    now = now or timezone.now()
    rules = rules if rules is not None else tagging.compile_rules()
    fetch_fn = fetch or http_fetch_youtube
    channels = channels or DEFAULT_CHANNELS

    all_entries = []
    failed_channels = []

    for ch in channels:
        feed_url = f"https://www.youtube.com/feeds/videos.xml?channel_id={ch['channel_id']}"
        try:
            body = fetch_fn(feed_url)
            entries = parse_youtube_feed(body)
            for e in entries:
                if not e.get("author") or e["author"] == "YouTube Channel":
                    e["author"] = ch["name"]
            all_entries.extend(entries)
        except YouTubeFetchError as exc:
            failed_channels.append(f"{ch['name']}: {exc}")

    if failed_channels and not all_entries:
        note = "; ".join(failed_channels)[:200]
        PollRun.objects.update_or_create(
            source=source, finished_at=now,
            defaults={"result": PollRun.Result.FAILED, "new_items": 0, "note": note},
        )
        return YouTubePassResult(source, PollRun.Result.FAILED, note=note)

    result_type = PollRun.Result.COMPLETE
    note = f"Partial: {'; '.join(failed_channels)}" if failed_channels else ""
    outcome = YouTubePassResult(source, result_type, seen=len(all_entries), note=note[:200])

    for entry in all_entries:
        item, created = Item.objects.get_or_create(
            source=source,
            external_id=entry["external_id"][:200],
            defaults={
                "url": entry["url"][:500],
                "author": entry["author"][:120],
                "title": entry["title"][:300],
                "excerpt": entry["excerpt"][:500],
                "summary": entry["summary"],
                "language": Item.Language.ENGLISH,
                "published_at": entry["published"],
                "collected_at": now,
            },
        )
        if created:
            outcome.new_items += 1
            for topic in tagging.tag(item, f"{entry['title']} {entry['summary']}", rules):
                outcome.tagged[topic.slug] = outcome.tagged.get(topic.slug, 0) + 1

    PollRun.objects.update_or_create(
        source=source, finished_at=now,
        defaults={"result": result_type, "new_items": outcome.new_items, "note": outcome.note},
    )
    return outcome

