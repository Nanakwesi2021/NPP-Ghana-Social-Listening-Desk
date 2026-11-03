"""X (Twitter) recent search collector adhering to desk rate-limiting and credential rules.

Uses X API v2 (GET /2/tweets/search/recent). Credentials live exclusively in the
environment variable X_BEARER_TOKEN. A missing token leaves the source in an awaiting state
without polling or failing other sources.

Rate-limiting governance (Decision 005):
- HTTP 429 or exhausted rate-limit headers record PollRun.Result.CAPPED.
- When results indicate truncation or pagination limits, the poll is marked CAPPED.
- Capped polls signal partial platform coverage in trend calculations without discarding
  received items.
"""
import http.client
import json
import os
import re
import socket
import ssl
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone as dt_timezone

import certifi
from django.db import transaction
from django.utils import timezone

from .. import tagging
from ..models import Item, PollRun, Source

USER_AGENT = "NPP-Ghana-Social-Listening-Desk/0.2 (internal research desk; X scanner)"
SEARCH_ENDPOINT = "https://api.twitter.com/2/tweets/search/recent"
DEFAULT_QUERY = '(NPP OR Bawumia OR Akufo-Addo OR "dumsor" OR "galamsey" OR "cedi" OR "PURC" OR "tariff") -is:retweet'
TIMEOUT_SECONDS = 15
MAX_BYTES = 5 * 1024 * 1024


class XFetchError(Exception):
    def __init__(self, message, status_code=None, is_rate_limit=False):
        super().__init__(message)
        self.status_code = status_code
        self.is_rate_limit = is_rate_limit


@dataclass
class XPassResult:
    source: Source
    result: str
    new_items: int = 0
    seen: int = 0
    note: str = ""
    tagged: dict = field(default_factory=dict)


def _tls_context():
    return ssl.create_default_context(cafile=certifi.where())


def get_bearer_token():
    return os.environ.get("X_BEARER_TOKEN", "").strip()


def ensure_x_source(sync=False):
    """Ensure the X source exists in the database. Defaults to kind=awaiting if no token is configured."""
    has_token = bool(get_bearer_token())
    kind = Source.Kind.COLLECTED if has_token else Source.Kind.AWAITING
    note = "" if has_token else "Awaiting X_BEARER_TOKEN in environment"
    source, created = Source.objects.get_or_create(
        key="x-recent-search",
        defaults={
            "name": "X",
            "group": "X",
            "detail": "Ghana-relevant queries",
            "platform": "x",
            "kind": kind,
            "method": "Recent search API · every 5 min",
            "scope": "English and Twi political terms, Ghana issues (dumsor, galamsey, tariffs). Capped at 100 posts.",
            "poll_interval_minutes": 5,
            "note": note,
            "position": 10,
        },
    )
    if sync and not created:
        source.kind = kind
        source.note = note
        source.save(update_fields=["kind", "note"])
    return source


def http_fetch_x(url, bearer_token):
    """Perform authenticated request to X API v2."""
    if not bearer_token:
        raise XFetchError("X_BEARER_TOKEN is not configured", status_code=401)
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {bearer_token}",
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS, context=_tls_context()) as response:
            remaining = response.headers.get("x-rate-limit-remaining")
            body = response.read(MAX_BYTES)
            return body, remaining
    except urllib.error.HTTPError as exc:
        is_429 = exc.code == 429
        try:
            err_data = json.loads(exc.read().decode("utf-8"))
            detail = err_data.get("detail", str(exc))
        except Exception:
            detail = str(exc)
        msg = f"HTTP {exc.code}: {detail}"
        raise XFetchError(msg, status_code=exc.code, is_rate_limit=is_429) from exc
    except (urllib.error.URLError, socket.timeout, TimeoutError, ConnectionError) as exc:
        reason = getattr(exc, "reason", exc)
        raise XFetchError(f"Could not connect to X API: {reason}") from exc
    except (http.client.HTTPException, OSError) as exc:
        raise XFetchError(f"Incomplete response from X API: {type(exc).__name__}") from exc


def parse_x_tweets(body):
    """Parse X API v2 JSON into (entries, is_capped, next_token)."""
    try:
        payload = json.loads(body)
    except ValueError as exc:
        raise XFetchError("Invalid JSON received from X API") from exc

    if "errors" in payload and not payload.get("data"):
        errors_desc = "; ".join(e.get("message", "Error") for e in payload["errors"])
        raise XFetchError(f"X API returned errors: {errors_desc}")

    tweets = payload.get("data") or []
    users = {u["id"]: u.get("username", "unknown") for u in (payload.get("includes", {}).get("users") or [])}
    meta = payload.get("meta") or {}
    next_token = meta.get("next_token")
    # If next_token exists, there are more tweets than the single-page limit returned
    is_capped = bool(next_token)

    entries = []
    for tweet in tweets:
        tweet_id = tweet.get("id", "").strip()
        if not tweet_id:
            continue
        author_id = tweet.get("author_id", "")
        username = users.get(author_id, "unknown")
        created_str = tweet.get("created_at")
        published = datetime.fromisoformat(created_str.replace("Z", "+00:00")) if created_str else None
        text = tweet.get("text", "")
        lang = tweet.get("lang", "en")
        language = Item.Language.ENGLISH
        if lang in ("ak", "tw") or re.search(r"[\u025B\u0254\u0190\u0186]", text):  # Twi characters ɛ, ɔ
            language = Item.Language.TWI

        entries.append({
            "external_id": f"x-{tweet_id}",
            "url": f"https://x.com/{username}/status/{tweet_id}",
            "author": f"@{username}",
            "excerpt": text,
            "title": "",
            "language": language,
            "published": published,
        })
    return entries, is_capped


@transaction.atomic
def collect_x(source=None, *, query=None, max_results=100, fetch=None, now=None, rules=None):
    """Collect recent political posts from X adhering to rate limits and decision 005."""
    source = source or ensure_x_source()
    now = now or timezone.now()
    rules = rules if rules is not None else tagging.compile_rules()
    token = get_bearer_token()

    if not token and fetch is None:
        note = "Skipped: X_BEARER_TOKEN is not configured"
        PollRun.objects.update_or_create(
            source=source, finished_at=now,
            defaults={"result": PollRun.Result.FAILED, "new_items": 0, "note": note},
        )
        return XPassResult(source, PollRun.Result.FAILED, note=note)

    query_str = query or DEFAULT_QUERY
    params = urllib.parse.urlencode({
        "query": query_str,
        "max_results": min(max(10, max_results), 100),
        "tweet.fields": "created_at,author_id,lang",
        "expansions": "author_id",
        "user.fields": "username",
    })
    url = f"{SEARCH_ENDPOINT}?{params}"

    fetch_fn = fetch or (lambda u: http_fetch_x(u, token))

    try:
        res = fetch_fn(url)
        if isinstance(res, tuple):
            body, remaining = res
        else:
            body, remaining = res, None
        entries, is_capped = parse_x_tweets(body)
        if remaining == "0":
            is_capped = True
    except XFetchError as exc:
        if exc.is_rate_limit:
            note = f"Rate limit reached (HTTP 429); partial coverage: {exc}"
            PollRun.objects.update_or_create(
                source=source, finished_at=now,
                defaults={"result": PollRun.Result.CAPPED, "new_items": 0, "note": note[:200]},
            )
            return XPassResult(source, PollRun.Result.CAPPED, note=note)
        note = str(exc)[:200]
        PollRun.objects.update_or_create(
            source=source, finished_at=now,
            defaults={"result": PollRun.Result.FAILED, "new_items": 0, "note": note},
        )
        return XPassResult(source, PollRun.Result.FAILED, note=note)

    result_type = PollRun.Result.CAPPED if is_capped else PollRun.Result.COMPLETE
    note = "Capped: provider rate limit or pagination ceiling" if is_capped else ""

    outcome = XPassResult(source, result_type, seen=len(entries), note=note)

    for entry in entries:
        item, created = Item.objects.get_or_create(
            source=source,
            external_id=entry["external_id"],
            defaults={
                "url": entry["url"][:500],
                "author": entry["author"][:120],
                "title": "",
                "excerpt": entry["excerpt"],
                "summary": entry["excerpt"],
                "language": entry["language"],
                "published_at": entry["published"],
                "collected_at": now,
            },
        )
        if created:
            outcome.new_items += 1
            for topic in tagging.tag(item, entry["excerpt"], rules):
                outcome.tagged[topic.slug] = outcome.tagged.get(topic.slug, 0) + 1

    PollRun.objects.update_or_create(
        source=source, finished_at=now,
        defaults={"result": result_type, "new_items": outcome.new_items, "note": outcome.note},
    )
    return outcome

