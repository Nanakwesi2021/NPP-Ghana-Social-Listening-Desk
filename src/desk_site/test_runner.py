"""Test runner that swaps Django's deliberately slow password hasher for a fast one.

Production keeps the strong default. Tests only need passwords to round-trip, and the
default hasher made the suite spend most of its minute hashing test passwords.
"""
from django.conf import settings
from django.test.runner import DiscoverRunner


class FastPasswordTestRunner(DiscoverRunner):
    def setup_test_environment(self, **kwargs):
        super().setup_test_environment(**kwargs)
        settings.PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
        # Most tests sign in with force_login, which skips the sign-in pages altogether, so two-step
        # sign-in is off unless a test turns it on (test_two_step.py does).
        settings.DESK_TWO_STEP_REQUIRED = False
