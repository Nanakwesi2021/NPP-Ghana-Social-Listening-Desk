"""Data model for the desk.

Observations (items) are stored once per source and external ID. Topics and subjects are
separate fields, so a report about a tariff can concern the government, the NPP, both or
neither. Trend windows and case decisions are persisted with their times so a shift can be
reconstructed later.
"""
from django.conf import settings
from django.contrib.postgres.indexes import GinIndex
from django.db import models


class Platform(models.TextChoices):
    NEWS = "news", "News"
    X = "x", "X"
    FACEBOOK = "facebook", "Facebook"
    INSTAGRAM = "instagram", "Instagram"
    THREADS = "threads", "Threads"
    TIKTOK = "tiktok", "TikTok"
    YOUTUBE = "youtube", "YouTube"
    WHATSAPP = "whatsapp", "WhatsApp"


class Subject(models.TextChoices):
    GOVERNMENT = "government", "Government"
    NPP = "npp", "NPP"
    BOTH = "both", "Government and NPP"
    UNASSIGNED = "unassigned", "Unassigned"


class Source(models.Model):
    class Kind(models.TextChoices):
        COLLECTED = "collected", "Collected"
        MANUAL = "manual", "Manual links"
        AWAITING = "awaiting", "Awaiting access"
        TIPS = "tips", "Tips"

    key = models.SlugField(unique=True)
    name = models.CharField(max_length=100)
    group = models.CharField(max_length=100, help_text="Row on the coverage page, e.g. News feeds.")
    detail = models.CharField(max_length=200, blank=True)
    platform = models.CharField(max_length=20, choices=Platform.choices)
    kind = models.CharField(max_length=20, choices=Kind.choices)
    method = models.CharField(max_length=200)
    scope = models.TextField()
    poll_interval_minutes = models.PositiveIntegerField(null=True, blank=True)
    feed_url = models.URLField(max_length=500, blank=True, help_text="RSS or Atom feed for collected news sources.")
    note = models.CharField(max_length=200, blank=True)
    position = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["position", "name"]

    def __str__(self):
        return self.name


class PollRun(models.Model):
    class Result(models.TextChoices):
        COMPLETE = "complete", "Complete"
        CAPPED = "capped", "Capped by the provider"
        FAILED = "failed", "Failed"

    source = models.ForeignKey(Source, on_delete=models.CASCADE, related_name="polls")
    finished_at = models.DateTimeField()
    result = models.CharField(max_length=20, choices=Result.choices)
    new_items = models.PositiveIntegerField(default=0)
    note = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ["-finished_at"]
        constraints = [models.UniqueConstraint(fields=["source", "finished_at"], name="one_poll_per_time")]


class Item(models.Model):
    class Language(models.TextChoices):
        ENGLISH = "en", "English"
        TWI = "tw", "Twi"
        PIDGIN = "pcm", "Ghanaian Pidgin"

    class TranslationStatus(models.TextChoices):
        NONE = "none", "No translation"
        DRAFT = "draft", "Draft translation · not yet reviewed"
        REVIEWED = "reviewed", "Reviewed translation"

    source = models.ForeignKey(Source, on_delete=models.CASCADE, related_name="items")
    external_id = models.CharField(max_length=200)
    url = models.URLField(max_length=500)
    author = models.CharField(max_length=120, help_text="Account, page or outlet.")
    title = models.CharField(max_length=300, blank=True)
    excerpt = models.TextField()
    summary = models.TextField(blank=True, help_text="Feed description as plain text; used for topic tagging.")
    language = models.CharField(max_length=5, choices=Language.choices, default=Language.ENGLISH)
    translation = models.TextField(blank=True)
    translation_status = models.CharField(
        max_length=10, choices=TranslationStatus.choices, default=TranslationStatus.NONE
    )
    translation_reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    translation_reviewed_at = models.DateTimeField(null=True, blank=True)
    published_at = models.DateTimeField(null=True, blank=True)
    collected_at = models.DateTimeField()
    origin = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.SET_NULL, related_name="copies",
        help_text="Set for syndicated or repeated copies; counts use the origin only.",
    )

    class Meta:
        ordering = ["published_at", "collected_at"]
        constraints = [models.UniqueConstraint(fields=["source", "external_id"], name="one_item_per_source_id")]
        indexes = [
            models.Index(fields=["collected_at"], name="desk_item_collected_idx"),
            GinIndex(fields=["excerpt"], opclasses=["gin_trgm_ops"], name="desk_item_excerpt_trgm"),
        ]

    def __str__(self):
        return f"{self.author}: {self.excerpt[:40]}"

    @property
    def observed_at(self):
        return self.published_at or self.collected_at

    @property
    def uses_collection_time(self):
        return self.published_at is None


class Topic(models.Model):
    slug = models.SlugField(unique=True)
    name = models.CharField(max_length=150)
    area = models.CharField(max_length=150, blank=True)
    subject = models.CharField(max_length=20, choices=Subject.choices, default=Subject.UNASSIGNED)
    subject_detail = models.CharField(max_length=150, blank=True)
    keywords = models.TextField(
        blank=True,
        help_text="One word or phrase per line, matched as whole words without regard to case. "
                  "Short all-capital acronyms (up to five letters, e.g. ECG, PURC) match only in capitals.",
    )
    items = models.ManyToManyField(Item, related_name="topics", blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    @property
    def subject_label(self):
        label = self.get_subject_display()
        return f"{label} · {self.subject_detail}" if self.subject_detail else label


class TrendCalculation(models.Model):
    as_of = models.DateTimeField(unique=True)
    window_minutes = models.PositiveIntegerField()
    min_mentions = models.PositiveIntegerField()
    below_threshold = models.PositiveIntegerField(default=0)
    partial_platforms = models.JSONField(default=list)
    computed_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-as_of"]


class TrendRow(models.Model):
    calculation = models.ForeignKey(TrendCalculation, on_delete=models.CASCADE, related_name="rows")
    topic = models.ForeignKey(Topic, on_delete=models.CASCADE, related_name="trend_rows")
    rank = models.PositiveIntegerField(null=True, blank=True)
    current_count = models.PositiveIntegerField()
    previous_count = models.PositiveIntegerField()
    change = models.IntegerField()
    platforms = models.JSONField(default=list)
    platform_counts = models.JSONField(default=dict)
    partial_platforms = models.JSONField(default=list)
    observed_label = models.CharField(max_length=200)
    buckets = models.JSONField(default=list)

    class Meta:
        ordering = ["rank", "-change"]
        constraints = [models.UniqueConstraint(fields=["calculation", "topic"], name="one_row_per_topic")]
        indexes = [
            GinIndex(fields=["platform_counts"], name="trendrow_pcounts_gin"),
            GinIndex(fields=["buckets"], name="trendrow_buckets_gin"),
        ]

    @property
    def is_new(self):
        return self.previous_count == 0 and self.current_count > 0


class Document(models.Model):
    """A primary record a claim can be checked against."""

    key = models.SlugField(unique=True)
    title = models.CharField(max_length=200)
    publisher = models.CharField(max_length=200)
    dated = models.DateField()
    url = models.URLField(max_length=500)
    summary = models.TextField(blank=True)
    key_line = models.TextField()
    is_sample = models.BooleanField(default=True)

    class Meta:
        ordering = ["-dated"]

    def __str__(self):
        return self.title


class Case(models.Model):
    class Urgency(models.TextChoices):
        ROUTINE = "l1", "Routine · L1"
        EMERGING = "l2", "Emerging · L2"
        URGENT = "l3", "Urgent · L3"
        CRITICAL = "l4", "Critical · L4"

    class Verification(models.TextChoices):
        UNVERIFIED = "unverified", "Unverified"
        IN_REVIEW = "in_review", "In review"
        SUPPORTED = "supported", "Supported"
        PARTLY = "partly", "Partly supported"
        NOT_SUPPORTED = "not_supported", "Not supported"
        INSUFFICIENT = "insufficient", "Insufficient evidence"

    class Status(models.TextChoices):
        NEW = "new", "New"
        ASSIGNED = "assigned", "Assigned"
        IN_REVIEW = "in_review", "In review"
        REVIEWED = "reviewed", "Reviewed · awaiting editor"
        CLOSED = "closed", "Closed"

    class Decision(models.TextChoices):
        NONE = "", "No decision"
        APPROVED = "approved", "Approved"
        ESCALATED = "escalated", "Escalated"
        CLOSED = "closed", "Closed"
        REOPENED = "reopened", "Reopened"
        SENT_BACK = "sent_back", "Sent back"

    FINDINGS = [
        Verification.SUPPORTED,
        Verification.PARTLY,
        Verification.NOT_SUPPORTED,
        Verification.INSUFFICIENT,
    ]

    ref = models.CharField(max_length=20, unique=True)
    claim = models.TextField()
    subject = models.CharField(max_length=20, choices=Subject.choices, default=Subject.UNASSIGNED)
    subject_detail = models.CharField(max_length=150, blank=True)
    topic = models.ForeignKey(Topic, null=True, blank=True, on_delete=models.SET_NULL, related_name="cases")
    origin_item = models.ForeignKey(Item, null=True, blank=True, on_delete=models.SET_NULL, related_name="cases")
    urgency = models.CharField(max_length=2, choices=Urgency.choices, default=Urgency.EMERGING)
    urgency_reason = models.CharField(max_length=300, blank=True)
    verification = models.CharField(max_length=20, choices=Verification.choices, default=Verification.UNVERIFIED)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.NEW)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="owned_cases"
    )
    owned_since = models.DateTimeField(null=True, blank=True)
    why_now = models.TextField()
    first_report_note = models.CharField(max_length=200, blank=True)
    next_action = models.CharField(max_length=300)
    due_at = models.DateTimeField()
    opened_at = models.DateTimeField()
    finding_rationale = models.TextField(blank=True)
    finding_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    finding_at = models.DateTimeField(null=True, blank=True)
    decision = models.CharField(max_length=20, choices=Decision.choices, blank=True, default="")
    decision_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    decision_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["due_at"]
        permissions = [("decide_case", "Can approve, escalate, close or reopen a case")]
        indexes = [
            GinIndex(fields=["claim"], opclasses=["gin_trgm_ops"], name="desk_case_claim_trgm"),
        ]

    def __str__(self):
        return self.ref

    @property
    def is_open(self):
        return self.status != self.Status.CLOSED

    @property
    def subject_label(self):
        label = self.get_subject_display()
        return f"{label} · {self.subject_detail}" if self.subject_detail else label

    @property
    def subject_short(self):
        if self.subject == Subject.UNASSIGNED and self.subject_detail:
            return self.subject_detail
        return self.get_subject_display()


class Evidence(models.Model):
    class Stance(models.TextChoices):
        PRIMARY = "primary", "Primary evidence"
        SUPPORTING = "supporting", "Supporting"
        CONTRARY = "contrary", "Contrary"

    case = models.ForeignKey(Case, on_delete=models.CASCADE, related_name="evidence")
    document = models.ForeignKey(Document, null=True, blank=True, on_delete=models.SET_NULL)
    title = models.CharField(max_length=200)
    publisher = models.CharField(max_length=200, blank=True)
    url = models.URLField(max_length=500)
    dated = models.DateField(null=True, blank=True)
    key_line = models.TextField(blank=True)
    stance = models.CharField(max_length=20, choices=Stance.choices, default=Stance.PRIMARY)
    cited = models.BooleanField(default=False)
    added_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")
    added_at = models.DateTimeField()

    class Meta:
        ordering = ["added_at", "id"]


class CaseEvent(models.Model):
    """Append-only decision log."""

    class Kind(models.TextChoices):
        SYSTEM = "system", "System"
        ANALYST = "analyst", "Analyst"
        EDITOR = "editor", "Editor"

    case = models.ForeignKey(Case, on_delete=models.CASCADE, related_name="events")
    at = models.DateTimeField()
    kind = models.CharField(max_length=10, choices=Kind.choices)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    actor_label = models.CharField(max_length=120)
    role_label = models.CharField(max_length=120, blank=True)
    action = models.TextField()
    note = models.TextField(blank=True)

    class Meta:
        ordering = ["at", "id"]


class CaseNotification(models.Model):
    """Dispatched or pending external alert for a critical case event."""

    class Channel(models.TextChoices):
        TELEGRAM = "telegram", "Telegram"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        SENT = "sent", "Sent"
        FAILED = "failed", "Failed"
        DISABLED = "disabled", "Disabled"

    case = models.ForeignKey(Case, on_delete=models.CASCADE, related_name="notifications")
    event = models.ForeignKey(CaseEvent, null=True, blank=True, on_delete=models.SET_NULL, related_name="notifications")
    channel = models.CharField(max_length=20, choices=Channel.choices, default=Channel.TELEGRAM)
    urgency = models.CharField(max_length=2, choices=Case.Urgency.choices)
    recipient = models.CharField(max_length=100, blank=True)
    dedupe_key = models.CharField(max_length=120, unique=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    message_text = models.TextField()
    external_message_id = models.CharField(max_length=100, blank=True)
    error_message = models.TextField(blank=True)
    created_at = models.DateTimeField()
    sent_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at", "-id"]

    def __str__(self):
        return f"{self.get_channel_display()} alert for {self.case.ref} ({self.get_status_display()})"


class ShiftClock(models.Model):
    """Anchors the Sample shift: sample time advances from sample_start at real speed."""

    sample_start = models.DateTimeField()
    real_start = models.DateTimeField()
