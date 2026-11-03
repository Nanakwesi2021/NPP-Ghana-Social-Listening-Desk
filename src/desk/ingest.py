"""Replay the Sample shift from tests/fixtures/sample_shift.

Every write is keyed (source + external ID for items, ref for cases, key for sources and
documents), so replaying the same files changes nothing that already exists: item counts,
trend rankings and the queue stay the same, and decisions made during a demo are kept.
"""
import json
from datetime import date, datetime

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import UNUSABLE_PASSWORD_PREFIX
from django.contrib.auth.models import Group, Permission
from django.db import transaction
from django.utils import timezone

from . import trends
from .models import (Case, CaseEvent, CaseNotification, Document, Evidence, Item, PollRun, ShiftClock, Source, Topic,
                     TrendCalculation)

EDITOR_GROUP = "Duty editor"
ANALYST_GROUP = "Analyst"


def _dt(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00")) if value else None


def _read(fixture_dir, name):
    return json.loads((fixture_dir / name).read_text(encoding="utf-8"))


def sample_people():
    """The fictional Sample shift people: the only accounts the passwordless demo sign-in may open.

    An account qualifies only if its username is listed in the sample fixture AND it has no
    usable password, so a real staff account can never be opened this way, even if someone
    gives it a sample username or leaves sample mode switched on.
    """
    try:
        usernames = [p["username"] for p in _read(settings.DESK_FIXTURE_DIR, "shift.json")["people"]]
    except (OSError, KeyError, ValueError):
        usernames = []
    return get_user_model().objects.filter(username__in=usernames, password__startswith=UNUSABLE_PASSWORD_PREFIX)


def ensure_groups():
    editors, _ = Group.objects.get_or_create(name=EDITOR_GROUP)
    Group.objects.get_or_create(name=ANALYST_GROUP)
    editors.permissions.add(Permission.objects.get(codename="decide_case", content_type__app_label="desk"))
    return editors


def reset():
    for model in (CaseNotification, CaseEvent, Evidence, Case, TrendCalculation, Item, PollRun, Source, Topic, Document, ShiftClock):
        model.objects.all().delete()


@transaction.atomic
def replay(fixture_dir, *, wipe=False):
    if wipe:
        reset()
    stats = {"items_new": 0, "items_repeated": 0, "cases_new": 0}
    shift = _read(fixture_dir, "shift.json")
    editors = ensure_groups()
    analysts = Group.objects.get(name=ANALYST_GROUP)
    User = get_user_model()
    users = {}
    for person in shift["people"]:
        user, created = User.objects.get_or_create(
            username=person["username"],
            defaults={"first_name": person["first_name"], "last_name": person["last_name"]},
        )
        if created:
            user.set_unusable_password()
            user.save()
        user.groups.add(editors if person["role"] == EDITOR_GROUP else analysts)
        users[person["username"]] = user

    topics = {}
    for t in shift["topics"]:
        topics[t["slug"]], _ = Topic.objects.get_or_create(slug=t["slug"], defaults={k: v for k, v in t.items() if k != "slug"})
    documents = {}
    for d in shift["documents"]:
        defaults = {k: v for k, v in d.items() if k != "key"}
        defaults["dated"] = date.fromisoformat(d["dated"])
        documents[d["key"]], _ = Document.objects.get_or_create(key=d["key"], defaults=defaults)

    src = _read(fixture_dir, "sources.json")
    sources = {}
    for i, s in enumerate(src["sources"]):
        sources[s["key"]], _ = Source.objects.get_or_create(
            key=s["key"], defaults={**{k: v for k, v in s.items() if k != "key"}, "position": i}
        )
    for p in src["polls"]:
        PollRun.objects.get_or_create(
            source=sources[p["source"]], finished_at=_dt(p["finished_at"]),
            defaults={"result": p["result"], "new_items": p["new_items"], "note": p["note"]},
        )

    copies = []

    def ingest(source_key, external_id, record):
        item, created = Item.objects.get_or_create(source=sources[source_key], external_id=external_id, defaults=record["defaults"])
        stats["items_new" if created else "items_repeated"] += 1
        if created:
            item.topics.set([topics[slug] for slug in record["topics"]])
            if record["copy_of"]:
                copies.append((item, record["copy_of"]))
        return item

    for e in _read(fixture_dir, "news.json")["entries"]:
        ingest(e["source"], e["guid"], {
            "topics": e["topics"], "copy_of": e["copy_of"],
            "defaults": {"url": e["link"], "author": sources[e["source"]].name, "title": e["title"], "excerpt": e["title"],
                         "language": e["language"], "published_at": _dt(e["published"]), "collected_at": _dt(e["collected"])},
        })
    for p in _read(fixture_dir, "social.json")["posts"]:
        ingest(p["source"], p["id"], {
            "topics": p["topics"], "copy_of": p["copy_of"],
            "defaults": {"url": p["url"], "author": p["account"], "excerpt": p["text"], "language": p["language"],
                         "translation": p["translation"], "translation_status": p["translation_status"],
                         "published_at": _dt(p["published"]), "collected_at": _dt(p["collected"])},
        })
    for item, ref in copies:
        item.origin = Item.objects.get(source=sources[ref["source"]], external_id=ref["id"])
        item.save(update_fields=["origin"])

    for c in _read(fixture_dir, "cases.json")["cases"]:
        if Case.objects.filter(ref=c["ref"]).exists():
            continue
        stats["cases_new"] += 1
        origin = c["origin_item"]
        case = Case.objects.create(
            ref=c["ref"], claim=c["claim"], subject=c["subject"], subject_detail=c["subject_detail"],
            topic=topics.get(c["topic"]),
            origin_item=Item.objects.get(source=sources[origin["source"]], external_id=origin["id"]) if origin else None,
            urgency=c["urgency"], urgency_reason=c["urgency_reason"], verification=c["verification"], status=c["status"],
            owner=users.get(c["owner"]), owned_since=_dt(c["owned_since"]), why_now=c["why_now"],
            first_report_note=c["first_report_note"], next_action=c["next_action"], due_at=_dt(c["due_at"]),
            opened_at=_dt(c["opened_at"]), finding_rationale=c["finding_rationale"], finding_by=users.get(c["finding_by"]),
            finding_at=_dt(c["finding_at"]), decision=c["decision"], decision_by=users.get(c["decision_by"]),
            decision_at=_dt(c["decision_at"]), closed_at=_dt(c["closed_at"]),
        )
        for ev in c["evidence"]:
            doc = documents[ev["document"]]
            Evidence.objects.create(case=case, document=doc, title=doc.title, publisher=doc.publisher, url=doc.url,
                                    dated=doc.dated, key_line=doc.key_line, stance=ev["stance"], cited=ev["cited"],
                                    added_by=users[ev["added_by"]], added_at=_dt(ev["added_at"]))
        for ev in c["events"]:
            actor = users.get(ev["actor"])
            CaseEvent.objects.create(
                case=case, at=_dt(ev["at"]), kind=ev["kind"], actor=actor,
                actor_label=actor.get_full_name() if actor else ev.get("actor_label", "System"),
                role_label=ev.get("role_label") or (EDITOR_GROUP if ev["kind"] == "editor" else ANALYST_GROUP if actor else ""),
                action=ev["action"], note=ev["note"],
            )

    as_of = _dt(shift["shift"]["as_of"])
    calc = trends.compute(as_of)
    ShiftClock.objects.get_or_create(defaults={"sample_start": as_of, "real_start": timezone.now()})
    stats["as_of"] = as_of
    stats["ranked"] = calc.rows.filter(rank__isnull=False).count()
    return stats
