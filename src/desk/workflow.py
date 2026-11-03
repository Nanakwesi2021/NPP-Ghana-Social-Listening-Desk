"""Case workflow: new → assigned → in review → reviewed → closed.

Analysts own cases, gather evidence and submit findings. Only users with desk.decide_case
(the Duty editor group) approve, escalate, close, reopen or send a finding back. Every
change appends a CaseEvent with its author, role and GMT time.
"""
from datetime import timedelta

from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Max

from . import clock
from .models import Case, CaseEvent, Evidence


class WorkflowError(Exception):
    pass


def role_label(user):
    if user.has_perm("desk.decide_case"):
        return "Duty editor"
    return "Analyst"


def display_name(user):
    return user.get_full_name() or user.get_username()


def _event(case, user, action, note="", kind=None):
    kind = kind or (CaseEvent.Kind.EDITOR if user.has_perm("desk.decide_case") else CaseEvent.Kind.ANALYST)
    return CaseEvent.objects.create(case=case, at=clock.now(), kind=kind, actor=user, actor_label=display_name(user),
                                    role_label=role_label(user), action=action, note=note)


def can_work(case, user):
    return case.owner_id == user.pk and case.status in (Case.Status.ASSIGNED, Case.Status.IN_REVIEW)


@transaction.atomic
def take_ownership(case, user):
    if case.status == Case.Status.CLOSED:
        raise WorkflowError("A closed case must be reopened by an editor first.")
    if case.owner_id and case.owner_id != user.pk:
        raise WorkflowError(f"{display_name(case.owner)} already owns this case.")
    case.owner = user
    case.owned_since = clock.now()
    case.status = Case.Status.IN_REVIEW
    if case.verification == Case.Verification.UNVERIFIED:
        case.verification = Case.Verification.IN_REVIEW
    case.next_action = "Compare the original with the primary evidence and submit a finding."
    case.save()
    _event(case, user, "Took ownership.", kind=CaseEvent.Kind.ANALYST)


@transaction.atomic
def release_ownership(case, user):
    if case.owner_id != user.pk:
        raise WorkflowError("Only the owner can release a case.")
    case.owner = None
    case.owned_since = None
    case.status = Case.Status.NEW
    if case.verification == Case.Verification.IN_REVIEW:
        case.verification = Case.Verification.UNVERIFIED
    case.next_action = "Assign a reviewer."
    case.save()
    _event(case, user, "Released ownership.", kind=CaseEvent.Kind.ANALYST)


@transaction.atomic
def add_evidence(case, user, *, document=None, title="", publisher="", url="", dated=None, key_line="",
                 stance=Evidence.Stance.PRIMARY):
    if not can_work(case, user):
        raise WorkflowError("Take ownership to add evidence.")
    if document:
        title, publisher, url, dated, key_line = document.title, document.publisher, document.url, document.dated, document.key_line
    evidence = Evidence.objects.create(case=case, document=document, title=title, publisher=publisher, url=url,
                                       dated=dated, key_line=key_line, stance=stance, added_by=user, added_at=clock.now())
    when = f" (dated {dated:%-d %b %Y})" if dated else ""
    _event(case, user, f"Added {evidence.get_stance_display().lower()}: {title}{when}.", kind=CaseEvent.Kind.ANALYST)
    return evidence


@transaction.atomic
def review_translation(case, user, text):
    item = case.origin_item
    if not can_work(case, user) or item is None:
        raise WorkflowError("Take ownership to review the translation.")
    if not text.strip():
        raise WorkflowError("Enter the reviewed translation.")
    item.translation = text.strip()
    item.translation_status = item.TranslationStatus.REVIEWED
    item.translation_reviewed_by = user
    item.translation_reviewed_at = clock.now()
    item.save()
    _event(case, user, f"Reviewed the English translation of the {item.get_language_display()} original.",
           kind=CaseEvent.Kind.ANALYST)


@transaction.atomic
def submit_finding(case, user, finding, rationale, cited_ids=()):
    if not can_work(case, user):
        raise WorkflowError("Only the owner can submit a finding.")
    if finding not in Case.FINDINGS:
        raise WorkflowError("Choose a finding.")
    if not rationale.strip():
        raise WorkflowError("Explain what the evidence shows.")
    case.evidence.update(cited=False)
    case.evidence.filter(pk__in=cited_ids).update(cited=True)
    case.verification = finding
    case.finding_rationale = rationale.strip()
    case.finding_by = user
    case.finding_at = clock.now()
    case.status = Case.Status.REVIEWED
    case.decision = Case.Decision.NONE
    case.next_action = "Duty editor: approve, escalate, close or send back."
    case.save()
    _event(case, user, f"Submitted finding: {case.get_verification_display()}.", note=case.finding_rationale,
           kind=CaseEvent.Kind.ANALYST)


def available_decisions(case):
    if case.status == Case.Status.CLOSED:
        return {"reopen"}
    actions = {"close"}
    if case.urgency != Case.Urgency.CRITICAL:
        actions.add("escalate")
    if case.status == Case.Status.REVIEWED and case.decision != Case.Decision.APPROVED:
        actions |= {"approve", "send_back"}
    return actions


@transaction.atomic
def decide(case, user, action, note="", next_action="", base_url=""):
    if not user.has_perm("desk.decide_case"):
        raise PermissionDenied("Only a duty editor can decide a case.")
    if action not in available_decisions(case):
        raise WorkflowError("That decision is not available for this case now.")
    now = clock.now()
    if action == "approve":
        case.decision = Case.Decision.APPROVED
        case.next_action = next_action.strip() or "Publish the correction note."
        case.due_at = now + timedelta(minutes=30)
        text = f"Approved the finding: {case.get_verification_display()}."
    elif action == "send_back":
        if not note.strip():
            raise WorkflowError("Say what the analyst should revise.")
        case.decision = Case.Decision.SENT_BACK
        case.status = Case.Status.IN_REVIEW
        case.next_action = "Analyst: revise the finding."
        text = "Sent the finding back to the analyst."
    elif action == "escalate":
        if not note.strip():
            raise WorkflowError("Record why the case is critical.")
        case.urgency = Case.Urgency.CRITICAL
        case.urgency_reason = f"Critical confirmed by {display_name(user)} at {now:%H:%M}."
        case.decision = Case.Decision.ESCALATED
        text = "Escalated to Critical · L4."
    elif action == "close":
        case.status = Case.Status.CLOSED
        case.closed_at = now
        case.decision = Case.Decision.CLOSED
        case.next_action = "None. Closed."
        text = "Closed the case."
    else:  # reopen
        case.status = Case.Status.IN_REVIEW if case.owner_id else Case.Status.NEW
        case.closed_at = None
        case.decision = Case.Decision.REOPENED
        case.next_action = "Review the new evidence. The earlier finding stays on record."
        case.due_at = now + timedelta(minutes=30)
        text = "Reopened the case. The earlier finding stays on record."
    case.decision_by = user
    case.decision_at = now
    case.save()
    event = _event(case, user, text, note=note.strip(), kind=CaseEvent.Kind.EDITOR)
    if action == "escalate":
        from . import notifications
        notifications.dispatch_case_alert(case, event=event, base_url=base_url)


def _next_ref():
    highest = Case.objects.aggregate(m=Max("ref"))["m"] or "ISS-0000"
    return f"ISS-{int(highest.split('-')[1]) + 1:04d}"


@transaction.atomic
def open_case_from_item(item, user):
    """Open (or return the existing) case for one source item."""
    origin = item.origin or item
    existing = Case.objects.filter(origin_item=origin).first()
    if existing:
        return existing, False
    topic = origin.topics.first()
    now = clock.now()
    case = Case.objects.create(
        ref=_next_ref(), claim=origin.translation or origin.excerpt, topic=topic, origin_item=origin,
        subject=topic.subject if topic else Case._meta.get_field("subject").default,
        subject_detail=topic.subject_detail if topic else "",
        urgency=Case.Urgency.EMERGING, why_now="Opened from a trend item. Set urgency once the claim is clear.",
        next_action="Confirm the exact claim and assign a reviewer.", due_at=now + timedelta(minutes=30), opened_at=now,
    )
    _event(case, user, f"Opened the case from an item on {origin.source.get_platform_display()} ({origin.author}).")
    return case, True
