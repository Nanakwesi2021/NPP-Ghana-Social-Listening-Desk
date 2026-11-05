from django.apps import AppConfig


class DeskConfig(AppConfig):
    name = "desk"
    verbose_name = "War Room"

    def ready(self):
        from . import signin  # noqa: F401  (connects the sign-in audit signal handlers)
