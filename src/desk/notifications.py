"""Telegram alert dispatcher for Critical · L4 escalations.

Builds and pushes alerts to a designated internal test chat when an issue is confirmed
Critical · L4. Deduplicates alerts so re-triggering does not send a second message, includes
direct links to the desk case file and primary evidence, and records delivery status so any
failure remains visible to the operator without blocking case decisions.
"""
import http.client
import json
import os
import socket
import ssl
import urllib.error
import urllib.request
from html import escape

import certifi

from . import clock
from .models import Case, CaseNotification


def _tls_context():
    return ssl.create_default_context(cafile=certifi.where())


def get_telegram_config():
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    base_url = os.environ.get("DESK_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
    return token, chat_id, base_url


def format_critical_alert(case, base_url="http://127.0.0.1:8000"):
    base_url = (base_url or "http://127.0.0.1:8000").rstrip("/")
    case_url = f"{base_url}/issues/{case.ref}/"
    topic_name = case.topic.name if case.topic else "Unassigned"
    urgency_reason = case.urgency_reason or case.why_now or "Critical confirmed by duty editor."

    lines = [
        "🚨 <b>CRITICAL · L4 ESCALATION</b>",
        "",
        f"<b>Case:</b> {escape(case.ref)}",
        f"<b>Subject:</b> {escape(case.subject_label)}",
        f"<b>Topic:</b> {escape(topic_name)}",
        f"<b>Verification:</b> {escape(case.get_verification_display())}",
        "",
        "<b>Claim:</b>",
        f"“{escape(case.claim)}”",
        "",
        "<b>Urgency Reason:</b>",
        escape(urgency_reason),
        "",
        f"🔗 <a href=\"{case_url}\">Open Case File on Desk ({escape(case.ref)})</a>",
    ]

    evidence_list = list(case.evidence.all())
    if evidence_list:
        lines.append("")
        lines.append("<b>Primary & Cited Evidence:</b>")
        for ev in evidence_list:
            stance = ev.get_stance_display()
            dated_str = f" ({ev.dated:%-d %b %Y})" if ev.dated else ""
            if ev.url:
                lines.append(f"• <a href=\"{escape(ev.url)}\">{escape(ev.title)}</a> — {escape(stance)}{dated_str}")
            else:
                lines.append(f"• {escape(ev.title)} — {escape(stance)}{dated_str}")

    if case.origin_item and case.origin_item.url:
        lines.append("")
        lines.append("<b>Original Item:</b>")
        platform = case.origin_item.source.get_platform_display()
        author = case.origin_item.author
        lines.append(f"• <a href=\"{escape(case.origin_item.url)}\">{escape(platform)} ({escape(author)})</a>")

    return "\n".join(lines)


def send_telegram_message(text, token, chat_id, parse_mode="HTML", timeout_seconds=8):
    """Deliver an alert via the Telegram Bot API."""
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": parse_mode,
        "disable_web_page_preview": False,
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Content-Type": "application/json",
            "User-Agent": "NPP-Ghana-Social-Listening-Desk/0.2 (internal alert dispatcher)",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout_seconds, context=_tls_context()) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            if body.get("ok"):
                msg_id = body.get("result", {}).get("message_id", "")
                return True, str(msg_id), ""
            return False, "", body.get("description", "Unknown Telegram error")
    except urllib.error.HTTPError as exc:
        try:
            err_body = json.loads(exc.read().decode("utf-8"))
            desc = err_body.get("description", str(exc))
        except Exception:
            desc = str(exc)
        return False, "", f"HTTP {exc.code}: {desc}"
    except (urllib.error.URLError, socket.timeout, TimeoutError, ConnectionError) as exc:
        reason = getattr(exc, "reason", exc)
        return False, "", f"Could not connect: {reason}"
    except (http.client.HTTPException, OSError) as exc:
        return False, "", f"Incomplete response: {type(exc).__name__}"


def dispatch_case_alert(case, event=None, base_url=None, force_retry=False):
    """Trigger an alert for a Critical · L4 case.

    Guarantees deduplication: once sent for L4, subsequent calls return the existing alert
    unless force_retry=True is specified. Unconfigured credentials or delivery failures do
    not raise an unhandled exception, keeping the case and its workflow fully operable.
    """
    if case.urgency != Case.Urgency.CRITICAL:
        return None

    dedupe_key = f"{case.ref}:l4"
    existing = CaseNotification.objects.filter(dedupe_key=dedupe_key).first()

    if existing and existing.status == CaseNotification.Status.SENT and not force_retry:
        return existing

    token, chat_id, default_base_url = get_telegram_config()
    effective_base_url = base_url or default_base_url
    message_text = format_critical_alert(case, base_url=effective_base_url)

    now = clock.now()
    if existing:
        notif = existing
        notif.event = event or notif.event
        notif.message_text = message_text
        notif.recipient = chat_id
        notif.status = CaseNotification.Status.PENDING
        notif.error_message = ""
        notif.save()
    else:
        notif = CaseNotification.objects.create(
            case=case,
            event=event,
            channel=CaseNotification.Channel.TELEGRAM,
            urgency=case.urgency,
            recipient=chat_id,
            dedupe_key=dedupe_key,
            status=CaseNotification.Status.PENDING,
            message_text=message_text,
            created_at=now,
        )

    if not token or not chat_id:
        notif.status = CaseNotification.Status.DISABLED
        notif.error_message = "Telegram alert not dispatched: TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID missing in environment."
        notif.save()
        return notif

    success, msg_id, error = send_telegram_message(message_text, token, chat_id)
    if success:
        notif.status = CaseNotification.Status.SENT
        notif.sent_at = clock.now()
        notif.external_message_id = msg_id
        notif.error_message = ""
    else:
        notif.status = CaseNotification.Status.FAILED
        notif.error_message = error
    notif.save()

    return notif

