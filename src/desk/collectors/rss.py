"""One-pass news collector for the named outlets: RSS or Atom feeds, or the public WordPress
posts API for outlets that have switched their RSS off.

Each pass records one PollRun per outlet: complete (with the number of new items) or failed
(with the error). A failing feed never stops the others. Items are keyed on the feed's guid,
or the entry link when no guid is given, so re-reading a feed adds nothing twice. Publication
and collection times are both kept; the trend windows fall back to collection time only when
a feed omits the date.
"""
import http.client
import json
import socket
import ssl
import urllib.error
import urllib.request
from calendar import timegm
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone as dt_timezone
from html import unescape
from pathlib import Path

import certifi
import feedparser
from django.db import transaction
from django.utils import timezone
from django.utils.html import strip_tags

from .. import tagging
from ..models import Item, PollRun, Source, Topic

CONFIG = Path(__file__).with_name("live_config.json")
USER_AGENT = "NPP-Ghana-Social-Listening-Desk/0.2 (internal research desk; RSS reader)"
TIMEOUT_SECONDS = 20
MAX_BYTES = 5 * 1024 * 1024


class FetchError(Exception):
    pass


@dataclass
class PassResult:
    source: Source
    result: str
    new_items: int = 0
    seen: int = 0
    note: str = ""
    tagged: dict = field(default_factory=dict)


def _tls_context():
    # Verify against the certifi bundle: some Python installs (e.g. python.org builds on macOS) ship
    # without system CA certificates. Verification is never turned off.
    return ssl.create_default_context(cafile=certifi.where())


def http_fetch(url):
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/rss+xml, application/xml;q=0.9, */*;q=0.5"})
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS, context=_tls_context()) as response:
            return response.read(MAX_BYTES)
    except urllib.error.HTTPError as exc:
        raise FetchError(f"HTTP {exc.code}") from exc
    except (urllib.error.URLError, socket.timeout, TimeoutError, ConnectionError) as exc:
        reason = getattr(exc, "reason", exc)
        raise FetchError(f"Could not connect: {reason}") from exc
    except (http.client.HTTPException, OSError) as exc:
        raise FetchError(f"Incomplete response: {type(exc).__name__}") from exc


def load_config():
    return json.loads(CONFIG.read_text(encoding="utf-8"))


def _feed_fields(feed):
    return {"feed_url": feed["url"], "kind": feed.get("kind", Source.Kind.COLLECTED),
            "method": feed.get("method", "RSS · every 5 min"), "note": feed.get("note", "")}


def ensure_sources(config=None, sync=False):
    """Create the configured outlets once; later edits in the admin are kept unless sync=True,
    which copies the feed address, kind, method and note from the config onto existing outlets."""
    config = config or load_config()
    sources = []
    for position, feed in enumerate(config["feeds"]):
        source, created = Source.objects.get_or_create(
            key=feed["key"],
            defaults={"name": feed["name"], "group": "News feeds", "detail": "Live news feed", "platform": "news",
                      "poll_interval_minutes": 5, "scope": "Ghanaian national news as published by the outlet.",
                      "position": position, **_feed_fields(feed)},
        )
        if sync and not created:
            for name, value in _feed_fields(feed).items():
                setattr(source, name, value)
            source.save()
        sources.append(source)
    return sources


def ensure_topics(config=None):
    """Seed the starting topics and keyword rules. Existing topics keep their edited rules."""
    config = config or load_config()
    for t in config["topics"]:
        Topic.objects.get_or_create(slug=t["slug"], defaults={
            "name": t["name"], "area": t["area"], "subject": t["subject"], "subject_detail": t["subject_detail"],
            "keywords": "\n".join(t["keywords"]),
        })


class ParseError(Exception):
    pass


@dataclass
class Entry:
    external_id: str
    link: str
    title: str
    summary: str
    published: datetime | None


def _entry_time(entry):
    parsed = entry.get("published_parsed") or entry.get("updated_parsed")
    if not parsed:
        return None
    return datetime.fromtimestamp(timegm(parsed), tz=dt_timezone.utc)


def _clean(text):
    return " ".join(unescape(strip_tags(text or "")).split())


def parse_rss(body):
    """RSS or Atom. Returns (entries, warning)."""
    parsed = feedparser.parse(body)
    if parsed.bozo and not parsed.entries:
        if body.lstrip()[:100].lower().startswith((b"<!doctype html", b"<html")):
            raise ParseError("Not a feed: the address returned a web page (check the feed URL)")
        raise ParseError(f"Malformed feed: {parsed.get('bozo_exception', 'unreadable')}")
    entries = [Entry(external_id=(e.get("id") or e.get("link", "")).strip(), link=e.get("link", ""),
                     title=_clean(e.get("title")), summary=_clean(e.get("summary")), published=_entry_time(e))
               for e in parsed.entries]
    return entries, "Parsed with warnings" if parsed.bozo else ""


def parse_wp_posts(body):
    """The public WordPress posts API (/wp-json/wp/v2/posts), used where an outlet has turned its RSS off."""
    try:
        posts = json.loads(body)
    except ValueError as exc:
        raise ParseError("Not a posts API response: invalid JSON") from exc
    if not isinstance(posts, list):
        raise ParseError("Not a posts API response: expected a list of posts")
    entries = []
    for post in posts:
        link = post.get("link", "")
        date_gmt = post.get("date_gmt")
        entries.append(Entry(
            external_id=link or f"wp-post:{post.get('id', '')}", link=link,
            title=_clean((post.get("title") or {}).get("rendered")),
            summary=_clean((post.get("excerpt") or {}).get("rendered")),
            published=datetime.fromisoformat(date_gmt).replace(tzinfo=dt_timezone.utc) if date_gmt else None,
        ))
    return entries, ""


def parser_for(url):
    return parse_wp_posts if "/wp-json/wp/v2/posts" in url else parse_rss


@transaction.atomic
def collect_source(source, *, fetch=None, now=None, rules=None):
    fetch = fetch or http_fetch
    now = now or timezone.now()
    rules = rules if rules is not None else tagging.compile_rules()

    def failed(note):
        PollRun.objects.update_or_create(source=source, finished_at=now,
                                         defaults={"result": PollRun.Result.FAILED, "new_items": 0, "note": note[:200]})
        return PassResult(source, PollRun.Result.FAILED, note=note)

    try:
        entries, warning = parser_for(source.feed_url)(fetch(source.feed_url))
    except (FetchError, ParseError) as exc:
        return failed(str(exc))

    outcome = PassResult(source, PollRun.Result.COMPLETE, seen=len(entries), note=warning)
    for entry in entries:
        external_id = entry.external_id[:200]
        if not external_id:
            continue
        title = entry.title[:300]
        item, created = Item.objects.get_or_create(
            source=source, external_id=external_id,
            defaults={"url": (entry.link or source.feed_url)[:500], "author": source.name, "title": title,
                      "excerpt": title or entry.summary[:300], "summary": entry.summary, "language": Item.Language.ENGLISH,
                      "published_at": entry.published, "collected_at": now},
        )
        if created:
            outcome.new_items += 1
            if title:
                published_time = entry.published or now
                original = Item.objects.filter(
                    origin__isnull=True,
                    published_at__gte=published_time - timedelta(hours=24),
                    published_at__lte=published_time + timedelta(hours=24),
                    title__iexact=title,
                ).exclude(pk=item.pk).first()
                if original:
                    item.origin = original
                    item.save(update_fields=["origin"])
            for topic in tagging.tag(item, f"{title} {entry.summary}", rules):
                outcome.tagged[topic.slug] = outcome.tagged.get(topic.slug, 0) + 1
    PollRun.objects.update_or_create(source=source, finished_at=now,
                                     defaults={"result": PollRun.Result.COMPLETE, "new_items": outcome.new_items, "note": outcome.note})
    return outcome


def collect(sources=None, *, fetch=None, now=None):
    now = now or timezone.now()
    if sources is None:
        sources = Source.objects.filter(kind=Source.Kind.COLLECTED).exclude(feed_url="")
    else:
        sources = [s for s in sources if s.kind == Source.Kind.COLLECTED and s.feed_url]
    rules = tagging.compile_rules()
    return [collect_source(source, fetch=fetch, now=now, rules=rules) for source in sources]


def retag(sources=None):
    """Re-apply the current keyword rules to stored items (after editing rules in the admin)."""
    rules = tagging.compile_rules()
    items = Item.objects.filter(origin__isnull=True)
    if sources is not None:
        items = items.filter(source__in=sources)
    changed = 0
    for item in items:
        before = set(item.topics.values_list("pk", flat=True))
        item.topics.set(tagging.matching_topics(f"{item.title} {item.summary or item.excerpt}", rules))
        changed += before != set(item.topics.values_list("pk", flat=True))
    return changed
