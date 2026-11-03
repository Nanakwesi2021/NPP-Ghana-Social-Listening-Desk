"""Provision, list, and manage real staff user accounts on the listening desk.

Enforces role assignment:
- Duty Editor: added to 'Duty editor' group with desk.decide_case permission.
- Analyst: added to 'Analyst' group.
- Superuser / Hub Admin: staff + superuser flags.
"""
import getpass
import secrets
import string

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError

from desk.ingest import ANALYST_GROUP, EDITOR_GROUP, ensure_groups


def generate_secure_password(length=16):
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*()-_=+"
    return "".join(secrets.choice(alphabet) for _ in range(length))


class Command(BaseCommand):
    help = "Provision or manage desk user accounts (Duty Editor or Analyst)."

    def add_arguments(self, parser):
        parser.add_argument("--username", help="Username for the desk account.")
        parser.add_argument("--name", help="Full name, e.g. 'Ama Owusu'.")
        parser.add_argument("--email", default="", help="Staff email address.")
        parser.add_argument("--role", choices=["editor", "analyst", "admin"], help="Desk role: editor, analyst, or admin.")
        parser.add_argument("--password", help="Password for the account (prompts if omitted).")
        parser.add_argument("--random-password", action="store_true", help="Generate a random 16-character secure password.")
        parser.add_argument("--superuser", action="store_true", help="Grant superuser and Django admin access.")
        parser.add_argument("--deactivate", action="store_true", help="Deactivate this user account.")
        parser.add_argument("--activate", action="store_true", help="Reactivate this user account.")
        parser.add_argument("--list", action="store_true", help="List all desk accounts and their roles.")

    def handle(self, *args, **options):
        ensure_groups()
        User = get_user_model()

        # Handle --list
        if options["list"]:
            users = User.objects.all().order_by("username")
            if not users.exists():
                self.stdout.write("No user accounts found.")
                return

            self.stdout.write(f"{'USERNAME':<15} {'NAME':<25} {'ROLE / GROUPS':<25} {'ACTIVE':<8} {'STAFF':<6}")
            self.stdout.write("-" * 80)
            for u in users:
                groups = ", ".join(g.name for g in u.groups.all()) or ("Superuser" if u.is_superuser else "None")
                active = "Yes" if u.is_active else "No"
                staff = "Yes" if u.is_staff else "No"
                name = u.get_full_name() or "(no name)"
                self.stdout.write(f"{u.username:<15} {name:<25} {groups:<25} {active:<8} {staff:<6}")
            return

        username = (options.get("username") or "").strip()
        if not username:
            raise CommandError("Specify --username or --list.")

        # Deactivate / Reactivate existing account
        if options["deactivate"]:
            try:
                user = User.objects.get(username=username)
                user.is_active = False
                user.save(update_fields=["is_active"])
                self.stdout.write(self.style.WARNING(f"User account '{username}' has been deactivated."))
                return
            except User.DoesNotExist:
                raise CommandError(f"User '{username}' does not exist.")

        if options["activate"]:
            try:
                user = User.objects.get(username=username)
                user.is_active = True
                user.save(update_fields=["is_active"])
                self.stdout.write(self.style.SUCCESS(f"User account '{username}' has been reactivated."))
                return
            except User.DoesNotExist:
                raise CommandError(f"User '{username}' does not exist.")

        # Create or update user
        role = options.get("role")
        if not role:
            raise CommandError("Specify --role (editor, analyst, or admin).")

        first_name, last_name = "", ""
        if options.get("name"):
            parts = options["name"].strip().split(None, 1)
            first_name = parts[0]
            last_name = parts[1] if len(parts) > 1 else ""

        user, created = User.objects.get_or_create(
            username=username,
            defaults={"first_name": first_name, "last_name": last_name, "email": options.get("email", "")},
        )

        if not created and options.get("name"):
            user.first_name = first_name
            user.last_name = last_name
        if options.get("email"):
            user.email = options["email"].strip()

        # Handle password
        password = options.get("password")
        if options["random_password"]:
            password = generate_secure_password(16)
            self.stdout.write(self.style.SUCCESS(f"Generated temporary password for {username}: {password}"))
        elif not password and created:
            # Interactive prompt if running in a terminal
            try:
                password = getpass.getpass(f"Enter password for {username}: ")
                confirm = getpass.getpass("Confirm password: ")
                if password != confirm:
                    raise CommandError("Passwords do not match.")
            except (EOFError, KeyboardInterrupt):
                password = generate_secure_password(16)
                self.stdout.write(self.style.NOTICE(f"No interactive TTY; generated random password: {password}"))

        if password:
            try:
                validate_password(password, user=user)
            except ValidationError as err:
                self.stdout.write(self.style.WARNING("Password validation warnings: " + "; ".join(err.messages)))
            user.set_password(password)

        # Set role and permissions
        editor_group = Group.objects.get(name=EDITOR_GROUP)
        analyst_group = Group.objects.get(name=ANALYST_GROUP)

        if role == "editor":
            user.groups.add(editor_group)
            user.groups.remove(analyst_group)
        elif role == "analyst":
            user.groups.add(analyst_group)
            user.groups.remove(editor_group)
        elif role == "admin":
            user.groups.add(editor_group)
            user.is_staff = True
            user.is_superuser = True

        if options["superuser"]:
            user.is_staff = True
            user.is_superuser = True

        user.is_active = True
        user.save()

        action = "Created" if created else "Updated"
        role_label = "Duty Editor" if role == "editor" else ("Analyst" if role == "analyst" else "Hub Admin")
        self.stdout.write(self.style.SUCCESS(f"{action} account '{username}' as {role_label}."))

