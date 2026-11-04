"""Submit an observed social link or field tip (Facebook, TikTok, WhatsApp, X).

Analyst-submitted links and field tips allow the desk to capture observations from
platforms without public APIs or from grassroots communication channels.

WhatsApp tips are tagged and routed to the topic and case queue for verification,
but are strictly excluded from trend momentum calculation per editorial rules.
"""
import re
import uuid

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from desk import tagging
from desk.collectors import x as x_collector, youtube as youtube_collector
from desk.models import Item, Platform, Source


def ensure_manual_source(platform):
    """Ensure a source exists for analyst-submitted manual links or field tips."""
    sources_config = {
        Platform.FACEBOOK: {
            "key": "facebook-links",
            "name": "Facebook",
            "group": "Facebook",
            "detail": "Named public pages",
            "kind": Source.Kind.MANUAL,
            "method": "Analyst-submitted links",
            "scope": "Public pages the desk may review. Not automated collection, so counts reflect submissions only.",
            "position": 30,
        },
        Platform.TIKTOK: {
            "key": "tiktok-links",
            "name": "TikTok",
            "group": "TikTok",
            "detail": "Analyst-submitted clips",
            "kind": Source.Kind.MANUAL,
            "method": "Analyst-submitted links",
            "scope": "Campaign videos and clips submitted for review.",
            "position": 40,
        },
        Platform.WHATSAPP: {
            "key": "whatsapp-tips",
            "name": "WhatsApp",
            "group": "WhatsApp tips",
            "detail": "Field and volunteer tips",
            "kind": Source.Kind.TIPS,
            "method": "Direct tip submissions",
            "scope": "Internal reports and early warnings. Tips trigger manual review but are NEVER counted in trend momentum.",
            "position": 70,
        },
        Platform.X: {
            "key": "x-recent-search",
            "name": "X",
            "group": "X",
            "detail": "Manual X submissions",
            "kind": Source.Kind.MANUAL,
            "method": "Analyst-submitted links",
            "scope": "Manually submitted X posts.",
            "position": 10,
        },
    }

    cfg = sources_config.get(platform)
    if not cfg:
        raise CommandError(f"Unsupported manual submission platform: '{platform}'. Choices: {list(sources_config.keys())}")

    source, _ = Source.objects.get_or_create(
        key=cfg["key"],
        defaults={
            "name": cfg["name"],
            "group": cfg["group"],
            "detail": cfg["detail"],
            "platform": platform,
            "kind": cfg["kind"],
            "method": cfg["method"],
            "scope": cfg["scope"],
            "position": cfg["position"],
        },
    )
    return source


def create_manual_social_item(platform, account, text, url="", title="", language_choice="", now=None):
    """Create and auto-tag an analyst-submitted social post, link or field tip."""
    source = ensure_manual_source(platform)
    now = now or timezone.now()
    external_id = f"{platform}-manual-{uuid.uuid4().hex[:12]}"
    if not url:
        url = f"https://desk.internal/{platform}/{external_id}"

    # Language detection
    if language_choice == "tw":
        language = Item.Language.TWI
    elif language_choice == "pcm":
        language = Item.Language.PIDGIN
    elif language_choice == "en":
        language = Item.Language.ENGLISH
    else:
        if re.search(r"[\u025B\u0254\u0190\u0186]", text) or any(w in text.lower().split() for w in ["ɛyɛ", "yie", "dɔɔso", "koraa"]):
            language = Item.Language.TWI
        else:
            language = Item.Language.ENGLISH

    item = Item.objects.create(
        source=source,
        external_id=external_id,
        url=url[:500],
        author=account[:120],
        title=(title or text[:80])[:200],
        excerpt=text,
        summary=text,
        language=language,
        published_at=now,
        collected_at=now,
    )

    rules = tagging.compile_rules()
    tagged_topics = tagging.tag(item, text, rules)
    return item, tagged_topics


class Command(BaseCommand):
    help = "Submit an analyst-observed social post, link or field tip."

    def add_arguments(self, parser):
        parser.add_argument("--platform", required=True, choices=["facebook", "tiktok", "whatsapp", "x"],
                            help="Platform of the submitted link or tip.")
        parser.add_argument("--account", required=True, help="Account name, page, or tip sender (e.g. 'Suame Traders').")
        parser.add_argument("--text", required=True, help="Text, transcript or claim quote.")
        parser.add_argument("--url", default="", help="Public URL of the post or video.")
        parser.add_argument("--title", default="", help="Optional short headline.")
        parser.add_argument("--language", choices=["en", "tw", "pcm"], default="",
                            help="Language: en (English), tw (Twi/Akan), pcm (Pidgin). Defaults to auto-detection.")

    def handle(self, *args, **options):
        platform = options["platform"]
        account = options["account"].strip()
        text = options["text"].strip()
        url = options.get("url", "").strip()
        title = options.get("title", "").strip()
        lang_choice = options.get("language")

        item, tagged_topics = create_manual_social_item(
            platform=platform,
            account=account,
            text=text,
            url=url,
            title=title,
            language_choice=lang_choice,
        )

        topic_names = ", ".join(t.name for t in tagged_topics) or "Untagged"
        tip_note = " (Field tip: excluded from trend momentum calculation per Decision 002)" if item.source.kind == Source.Kind.TIPS else ""
        self.stdout.write(self.style.SUCCESS(
            f"Submitted {item.source.name} item #{item.pk} from {account} [{item.get_language_display()}].\n"
            f"Topics: {topic_names}{tip_note}\n"
            f"URL: {item.url}"
        ))

