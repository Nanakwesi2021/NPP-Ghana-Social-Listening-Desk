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
