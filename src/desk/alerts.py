"""Cross-network spike and trending breakout detection engine.

Scans computed trend rows to identify topics that are breaking out across multiple
monitored networks (News Portals, YouTube, X, Facebook, TikTok) or exhibiting rapid
velocity surges. Automatically dispatches alerts to internal channels (e.g. Telegram)
with deduplication per hour window and surge tier to avoid alert fatigue.
"""
from html import escape
import os

from django.db import transaction

from . import clock
from .models import Platform, TrendAlert, TrendCalculation, TrendRow
from .notifications import get_telegram_config, send_telegram_message


def classify_breakout(row):
    """Determine whether a trend row qualifies as a breakout and assign its type and tier.

    Returns:
        (is_breakout, alert_type, tier)
        or (False, None, None) if criteria are not met.
    """
    if row.current_count < 5 or row.change <= 0:
        return False, None, None

    n_platforms = len(row.platforms)
    is_cross = n_platforms >= 2
    is_surge = row.change >= 5

    if not is_cross and not is_surge:
        return False, None, None

    if is_cross and is_surge:
        alert_type = TrendAlert.AlertType.BREAKOUT
    elif is_cross:
        alert_type = TrendAlert.AlertType.CROSS_NETWORK
    else:
        alert_type = TrendAlert.AlertType.VELOCITY_SURGE

    if row.change >= 10:
        tier = "surge_high"
    elif row.change >= 5:
        tier = "surge_med"
    else:
        tier = "breakout"

    return True, alert_type, tier


def format_trend_alert(row, calc, alert_type=None, base_url=None):
    """Build the HTML Telegram notification for a trending breakout."""
    _, _, default_base_url = get_telegram_config()
    base_url = (base_url or default_base_url or "http://127.0.0.1:8000").rstrip("/")
    topic_url = f"{base_url}/trends/{row.topic.slug}/"

    type_titles = {
        TrendAlert.AlertType.BREAKOUT: "KEY TRENDING BREAKOUT",
        TrendAlert.AlertType.CROSS_NETWORK: "CROSS-NETWORK SPIKE",
        TrendAlert.AlertType.VELOCITY_SURGE: "HIGH-VELOCITY SURGE",
    }
    title = type_titles.get(alert_type or getattr(row, "alert_type", TrendAlert.AlertType.BREAKOUT), "TRENDING BREAKOUT")
    subject_label = row.topic.subject_label

    lines = [
        f"⚡ <b>{title}</b>",
        "",
        f"<b>Topic:</b> {escape(row.topic.name)}",
        f"<b>Subject:</b> {escape(subject_label)}",
        f"<b>Momentum:</b> <b>{row.current_count}</b> mentions this hour (+{row.change} vs previous hour)",
        f"<b>Networks:</b> {escape(row.observed_label)}",
    ]

    if row.platform_counts:
        lines.append("")
        lines.append("<b>Platform Breakdown:</b>")
        platform_labels = dict(Platform.choices)
        for platform_key, count in sorted(row.platform_counts.items(), key=lambda x: (-x[1], x[0])):
            label = platform_labels.get(platform_key, platform_key.title())
            lines.append(f"• {escape(label)}: {count}")

    lines.append("")
    lines.append(f"🔗 <a href=\"{topic_url}\">View Trend on Desk ({escape(row.topic.name)})</a>")
    return "\n".join(lines)


def dispatch_trend_alert(row, calc, base_url=None, force_retry=False):
    """Create and push a TrendAlert for a qualifying breakout row.

    Deduplicates on topic, window hour, and surge tier so repeated runs do not spam
    the internal chat.
    """
    is_breakout, alert_type, tier = classify_breakout(row)
    if not is_breakout:
        return None

    hour_str = calc.as_of.strftime("%Y%m%d%H")
    dedupe_key = f"trend:{row.topic.slug}:{hour_str}:{tier}"

    existing = TrendAlert.objects.filter(dedupe_key=dedupe_key).first()
    if existing and existing.status == TrendAlert.Status.SENT and not force_retry:
        return existing

    token, chat_id, default_base = get_telegram_config()
    effective_base = base_url or default_base
    message_text = format_trend_alert(row, calc, alert_type=alert_type, base_url=effective_base)

    now = clock.now()
    if existing:
        alert = existing
        alert.current_count = row.current_count
        alert.previous_count = row.previous_count
        alert.change = row.change
        alert.rank = row.rank
        alert.platforms = row.platforms
        alert.platform_counts = row.platform_counts
        alert.observed_label = row.observed_label
        alert.message_text = message_text
        alert.recipient = chat_id
        alert.status = TrendAlert.Status.PENDING
        alert.error_message = ""
        alert.save()
    else:
        alert = TrendAlert.objects.create(
            topic=row.topic,
            calculation=calc,
            rank=row.rank,
            current_count=row.current_count,
            previous_count=row.previous_count,
            change=row.change,
            platforms=row.platforms,
            platform_counts=row.platform_counts,
            observed_label=row.observed_label,
            alert_type=alert_type,
            tier=tier,
            channel=TrendAlert.Channel.TELEGRAM,
            recipient=chat_id,
            dedupe_key=dedupe_key,
            status=TrendAlert.Status.PENDING,
            message_text=message_text,
            created_at=now,
        )

    if not token or not chat_id:
        alert.status = TrendAlert.Status.DISABLED
        alert.error_message = "Telegram push disabled: TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID missing in environment."
        alert.save()
        return alert

    success, msg_id, error = send_telegram_message(message_text, token, chat_id)
    if success:
        alert.status = TrendAlert.Status.SENT
        alert.sent_at = clock.now()
        alert.external_message_id = msg_id
        alert.error_message = ""
    else:
        alert.status = TrendAlert.Status.FAILED
        alert.error_message = error
    alert.save()
    return alert


def detect_and_dispatch_trend_alerts(calc, base_url=None, force_retry=False):
    """Scan all rows of a calculation and dispatch alerts for all detected breakouts.

    Returns a list of TrendAlert instances.
    """
    alerts = []
    rows = calc.rows.select_related("topic").order_by("rank", "-change")
    for row in rows:
        alert = dispatch_trend_alert(row, calc, base_url=base_url, force_retry=force_retry)
        if alert:
            alerts.append(alert)
    return alerts
