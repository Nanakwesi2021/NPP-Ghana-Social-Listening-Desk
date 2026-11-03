from django.contrib import admin

from .models import Case, CaseEvent, Document, Evidence, Item, PollRun, SignInEvent, Source, Topic
from .signin import LockoutAdminAuthenticationForm


@admin.register(Source)
class SourceAdmin(admin.ModelAdmin):
    list_display = ("name", "group", "platform", "kind", "poll_interval_minutes")
    list_filter = ("platform", "kind")


@admin.register(PollRun)
class PollRunAdmin(admin.ModelAdmin):
    list_display = ("source", "finished_at", "result", "new_items")
    list_filter = ("source", "result")


@admin.register(Item)
class ItemAdmin(admin.ModelAdmin):
    list_display = ("author", "source", "published_at", "collected_at", "language", "origin")
    list_filter = ("source", "language")
    search_fields = ("excerpt", "author", "external_id")


@admin.register(Topic)
class TopicAdmin(admin.ModelAdmin):
    list_display = ("name", "subject", "subject_detail", "area")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ("title", "publisher", "dated", "is_sample")


class EvidenceInline(admin.TabularInline):
    model = Evidence
    extra = 0


class CaseEventInline(admin.TabularInline):
    model = CaseEvent
    extra = 0
    can_delete = False
    readonly_fields = ("at", "kind", "actor", "actor_label", "role_label", "action", "note")

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Case)
class CaseAdmin(admin.ModelAdmin):
    list_display = ("ref", "claim", "urgency", "verification", "status", "owner", "due_at")
    list_filter = ("urgency", "verification", "status", "subject")
    search_fields = ("ref", "claim")
    inlines = [EvidenceInline, CaseEventInline]


admin.site.login_form = LockoutAdminAuthenticationForm


@admin.register(SignInEvent)
class SignInEventAdmin(admin.ModelAdmin):
    """Read-only sign-in audit log."""

    list_display = ("at", "username", "outcome", "ip", "user_agent")
    list_filter = ("outcome",)
    search_fields = ("username", "ip")
    date_hierarchy = "at"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
